#!/usr/bin/env python3
"""Run a focused real-LLM version of the Search-as-Code matrix.

This runner replaces the rule-backed QR/router/planner/reflection decisions
with structured LLM calls. It intentionally defaults to the same 5-query sample
used by the real codegen retest; full-dataset multi-turn LLM runs are expensive
and less repeatable.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import time
from typing import Any

from llm_search_codegen import DEFAULT_CODEX_CLI, LLMSearchCodeGenerator, default_model
from real_search_stack.apis import (
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryRewriteAPI,
    RealQueryUnderstandingAPI,
    RealRankingAPI,
    SearchCandidate,
)
from run_experiment_matrix import (
    authority_score,
    authority_aware_topk,
    candidate_to_row,
    execute_preset_stack,
    execute_preset_stacks,
    preselect_goal_evidence,
    route_preset_stacks,
)
from run_flow_comparison import FlowContext, QueryStats, merge_runtime_candidates, unique_runtime
from run_real_codegen_retest import (
    DEFAULT_TASK_IDS,
    execute_real_agentic_code,
    execute_real_code_with_repair,
)
from run_sac_dataset_benchmark import (
    DATASET_DIR,
    build_iterative_agentic_strategy,
    evaluate_query_at_ks,
    evaluate_results,
    load_dataset,
    read_json,
    relevant_doc_ids,
    summarize_stats,
)


STACKS = [
    "general_hybrid",
    "alias_resolution",
    "exact_security",
    "wide_fanout",
    "negative_evidence",
    "authority",
    "policy",
    "semantic_multihop",
]

INITIAL_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rewrites": {
            "type": "array",
            "items": {"type": "string"},
            "description": "1-3 concise retrieval rewrites. Preserve exact IDs and versions.",
        },
        "preset_stacks": {
            "type": "array",
            "items": {"type": "string", "enum": STACKS},
            "description": "1-3 preset stacks to run initially, ordered by priority.",
        },
        "decomposed_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "1-3 subqueries for an agentic fixed-flow tool caller.",
        },
        "evidence_goals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Evidence categories that should be present before stopping.",
        },
        "stop_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete stop conditions that prove the query has enough evidence.",
        },
        "must_preserve_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exact IDs, aliases, versions, customer names, or negation terms to preserve.",
        },
        "preferred_search_style": {
            "type": "string",
            "enum": ["exact", "semantic", "authority", "wide_fanout", "policy", "mixed"],
            "description": "Primary retrieval style implied by the query.",
        },
        "rationale": {"type": "string"},
    },
    "required": [
        "rewrites",
        "preset_stacks",
        "decomposed_queries",
        "evidence_goals",
        "stop_requirements",
        "must_preserve_terms",
        "preferred_search_style",
        "rationale",
    ],
    "additionalProperties": False,
}

REFLECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "needs_followup": {"type": "boolean"},
        "followup_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Additional fixed-flow tool queries if evidence is incomplete.",
        },
        "followup_stacks": {
            "type": "array",
            "items": {"type": "string", "enum": STACKS},
            "description": "Additional preset stacks if evidence is incomplete.",
        },
        "covered_evidence_goals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Evidence goals that appear covered by observed docs.",
        },
        "missing_evidence_goals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Evidence goals still missing or under-supported.",
        },
        "confident_doc_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observed doc ids that should be protected in final evidence ranking.",
        },
        "stop_reason": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": [
        "needs_followup",
        "followup_queries",
        "followup_stacks",
        "covered_evidence_goals",
        "missing_evidence_goals",
        "confident_doc_ids",
        "stop_reason",
        "rationale",
    ],
    "additionalProperties": False,
}


SYSTEM_DEFINITIONS = {
    "real_fixed_flow_llm_qr": "query -> real LLM QR -> multi-query hybrid retrieval -> rerank",
    "real_preset_flow_llm_router": "query -> real LLM router -> one preset search stack -> rerank",
    "real_agentic_fixed_flow_llm_reflection": "query -> real LLM planner -> fixed-flow calls -> real LLM reflection -> iterate",
    "real_agentic_preset_flow_llm_reflection": "query -> real LLM router -> preset stacks -> real LLM reflection -> iterate",
    "real_one_shot_code_gen": "query -> real LLM Python code generation -> execute -> results",
    "real_agentic_code_gen": "query -> real LLM planner/codegen -> execute -> real LLM reflection/codegen -> execute",
}


class LLMDecisionGenerator:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        timeout_seconds: int,
        cache_dir: str | Path,
        codex_cli: str,
        codex_reasoning_effort: str,
    ) -> None:
        if provider != "codex-cli":
            raise ValueError("run_real_llm_matrix currently supports provider=codex-cli")
        self.provider = provider
        self.model = model or default_model(provider)
        self.timeout_seconds = timeout_seconds
        self.cache_dir = Path(cache_dir)
        self.codex_cli = codex_cli
        self.codex_reasoning_effort = codex_reasoning_effort
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def initial_decision(self, query: str, *, analysis: dict, category: str, difficulty: str) -> dict:
        prompt = build_initial_decision_prompt(query, analysis=analysis, category=category, difficulty=difficulty)
        return self._generate_json("initial", query, prompt, INITIAL_DECISION_SCHEMA)

    def reflection(self, query: str, observation: dict, *, mode: str) -> dict:
        prompt = build_reflection_prompt(query, observation, mode=mode)
        return self._generate_json(f"reflection_{mode}", query, prompt, REFLECTION_SCHEMA)

    def _generate_json(self, kind: str, query: str, prompt: str, schema: dict[str, Any]) -> dict:
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "provider": self.provider,
                    "model": self.model,
                    "reasoning": self.codex_reasoning_effort,
                    "kind": kind,
                    "query": query,
                    "prompt": prompt,
                    "schema": schema,
                    "prompt_version": 2,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:24]
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            payload["cache_hit"] = True
            return payload

        if not Path(self.codex_cli).exists():
            raise RuntimeError(f"Codex CLI not found: {self.codex_cli}")
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="real-llm-decision-") as tmp:
            tmp_path = Path(tmp)
            schema_path = tmp_path / "schema.json"
            output_path = tmp_path / "output.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            cmd = [
                self.codex_cli,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--cd",
                str(Path(__file__).resolve().parent),
                "-c",
                f"model_reasoning_effort={json.dumps(self.codex_reasoning_effort)}",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
            ]
            if self.model:
                cmd.extend(["--model", self.model])
            cmd.append(prompt)
            completed = subprocess.run(
                cmd,
                cwd=str(Path(__file__).resolve().parent),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"Codex CLI decision failed with exit {completed.returncode}:\n{completed.stdout[-4000:]}")
            if not output_path.exists():
                raise RuntimeError(f"Codex CLI did not write structured output:\n{completed.stdout[-4000:]}")
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        payload = sanitize_decision_payload(payload)
        payload.update(
            {
                "provider": self.provider,
                "model": self.model,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
            }
        )
        cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused real LLM Search-as-Code matrix.")
    parser.add_argument("--data-dir", default=str(DATASET_DIR))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    parser.add_argument("--task-ids", default=DEFAULT_TASK_IDS)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-k", default="10")
    parser.add_argument("--candidate-k", type=int, default=120)
    parser.add_argument("--tool-candidate-k", type=int, default=120)
    parser.add_argument("--max-reflection-rounds", type=int, default=2)
    parser.add_argument("--systems", default=",".join(SYSTEM_DEFINITIONS))
    parser.add_argument("--provider", default="codex-cli", choices=["codex-cli"])
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cache-dir", default=".llm_codegen_cache/real_llm_matrix")
    parser.add_argument("--codex-cli", default=DEFAULT_CODEX_CLI)
    parser.add_argument("--codex-reasoning-effort", default="low")
    parser.add_argument("--output", default="real_llm_matrix_results.json")
    parser.add_argument("--report", default="real_llm_matrix_report.md")
    parser.add_argument("--comparison", default="experiment_matrix_results.json")
    parser.add_argument("--wikidata", action="store_true")
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if args.offline_models:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    data_dir = Path(args.data_dir)
    documents, tasks, qrels, hard_negatives = load_dataset(data_dir, split=args.split)
    wanted = {item.strip() for item in args.task_ids.split(",") if item.strip()}
    tasks = [task for task in tasks if task["task_id"] in wanted]
    missing = wanted - {task["task_id"] for task in tasks}
    if missing:
        raise SystemExit(f"Unknown or filtered-out task ids: {', '.join(sorted(missing))}")
    if not tasks:
        raise SystemExit("No tasks selected")
    metrics_k = sorted({int(item) for item in args.metrics_k.split(",") if item.strip()})

    selected = [item.strip() for item in args.systems.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(SYSTEM_DEFINITIONS))
    if unknown:
        raise SystemExit(f"Unknown systems: {', '.join(unknown)}")

    print(f"Dataset: {data_dir}")
    print(f"Tasks: {len(tasks)}")
    print(f"Task ids: {', '.join(task['task_id'] for task in tasks)}")
    print(f"Systems: {', '.join(selected)}")
    print("Loading tools...")
    query_understanding_api = RealQueryUnderstandingAPI()
    entity_linking_api = RealEntityLinkingAPI(wikidata_enabled=args.wikidata)
    query_rewrite_api = RealQueryRewriteAPI()
    search_api = RealHybridSearchAPI(documents, local_files_only=args.offline_models)
    ranking_api = RealRankingAPI(local_files_only=args.offline_models)

    decider = LLMDecisionGenerator(
        provider=args.provider,
        model=args.model,
        timeout_seconds=args.timeout,
        cache_dir=Path(args.cache_dir) / "decisions",
        codex_cli=args.codex_cli,
        codex_reasoning_effort=args.codex_reasoning_effort,
    )
    one_shot_generator = LLMSearchCodeGenerator(
        provider=args.provider,
        model=args.model,
        timeout_seconds=args.timeout,
        cache_dir=".llm_codegen_cache/real_codegen_retest/one_shot",
        codex_cli=args.codex_cli,
        codex_reasoning_effort=args.codex_reasoning_effort,
    )
    agentic_generator = LLMSearchCodeGenerator(
        provider=args.provider,
        model=args.model,
        timeout_seconds=args.timeout,
        cache_dir=".llm_codegen_cache/real_codegen_retest/agentic",
        codex_cli=args.codex_cli,
        codex_reasoning_effort=args.codex_reasoning_effort,
    )

    initial_decisions = build_initial_decisions(
        tasks,
        decider,
        query_understanding_api=query_understanding_api,
    )

    task_queries = {task["task_id"]: task["query"] for task in tasks}
    task_by_id = {task["task_id"]: task for task in tasks}
    systems: dict[str, dict] = {}

    def maybe_run(system: str, executor) -> None:
        if system not in selected:
            return
        systems[system] = run_real_system(
            system,
            task_queries,
            task_by_id,
            qrels,
            hard_negatives,
            args.top_k,
            metrics_k,
            executor,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
        )

    maybe_run(
        "real_fixed_flow_llm_qr",
        lambda qid, ctx: run_real_fixed_flow_llm_qr(
            ctx,
            initial_decisions[qid],
            candidate_k=args.candidate_k,
            top_k=args.top_k,
        ),
    )
    maybe_run(
        "real_preset_flow_llm_router",
        lambda qid, ctx: run_real_preset_flow_llm_router(
            ctx,
            initial_decisions[qid],
            candidate_k=args.candidate_k,
            top_k=args.top_k,
        ),
    )
    maybe_run(
        "real_agentic_fixed_flow_llm_reflection",
        lambda qid, ctx: run_real_agentic_fixed_flow_llm_reflection(
            ctx,
            initial_decisions[qid],
            decider,
            tool_candidate_k=args.tool_candidate_k,
            final_candidate_k=args.candidate_k,
            top_k=args.top_k,
            max_reflection_rounds=args.max_reflection_rounds,
        ),
    )
    maybe_run(
        "real_agentic_preset_flow_llm_reflection",
        lambda qid, ctx: run_real_agentic_preset_flow_llm_reflection(
            ctx,
            initial_decisions[qid],
            decider,
            tool_candidate_k=args.tool_candidate_k,
            final_candidate_k=args.candidate_k,
            top_k=args.top_k,
            max_reflection_rounds=args.max_reflection_rounds,
        ),
    )
    benchmark_hint = (
        "custom enterprise Search-as-Code benchmark; retrieval must handle exact ids, aliases, "
        "authority/source-of-truth disambiguation, policy lookups, negative evidence, and multi-hop joins"
    )
    maybe_run(
        "real_one_shot_code_gen",
        lambda qid, ctx: run_real_one_shot_codegen(
            ctx,
            one_shot_generator,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            benchmark_hint=benchmark_hint,
        ),
    )
    maybe_run(
        "real_agentic_code_gen",
        lambda qid, ctx: run_real_agentic_codegen(
            ctx,
            agentic_generator,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            benchmark_hint=benchmark_hint,
        ),
    )

    comparison = load_rule_comparison(args.comparison, [task["task_id"] for task in tasks], k=max(metrics_k))
    manifest = read_json(data_dir / "manifest.json")
    output = {
        "dataset": manifest.get("dataset_version", "unknown"),
        "split": args.split,
        "documents": len(documents),
        "tasks": len(tasks),
        "task_ids": [task["task_id"] for task in tasks],
        "top_k": args.top_k,
        "metrics_k": metrics_k,
        "candidate_k": args.candidate_k,
        "tool_candidate_k": args.tool_candidate_k,
        "max_reflection_rounds": args.max_reflection_rounds,
        "planning_reflection_version": 2,
        "provider": args.provider,
        "model": args.model or default_model(args.provider),
        "codex_reasoning_effort": args.codex_reasoning_effort,
        "systems": systems,
        "summary_rows": build_summary_rows(systems, metrics_k),
        "rule_matrix_subset": comparison,
        "initial_decisions": initial_decisions,
        "per_query_comparison": build_per_query_comparison(systems, task_by_id, qrels, metrics_k),
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    Path(args.report).write_text(render_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def build_initial_decisions(tasks: list[dict], decider: LLMDecisionGenerator, *, query_understanding_api: RealQueryUnderstandingAPI) -> dict[str, dict]:
    decisions = {}
    print("Generating real LLM initial decisions...")
    for task in tasks:
        analysis = query_understanding_api.analyze(task["query"])
        decision = decider.initial_decision(
            task["query"],
            analysis=analysis,
            category=task.get("category", ""),
            difficulty=task.get("difficulty", ""),
        )
        decision = normalize_initial_decision(decision, fallback_query=task["query"])
        decisions[task["task_id"]] = decision
        print(
            f"  {task['task_id']}: stacks={decision['preset_stacks']} "
            f"rewrites={len(decision['rewrites'])} decomposed={len(decision['decomposed_queries'])} "
            f"llm_ms={decision.get('latency_ms', 0):.1f} cache={decision.get('cache_hit')}"
        )
    return decisions


def run_real_system(
    name: str,
    queries: dict[str, str],
    task_by_id: dict[str, dict],
    qrels: dict,
    hard_negatives: dict[str, set[str]],
    top_k: int,
    metrics_k: list[int],
    executor,
    *,
    query_understanding_api: RealQueryUnderstandingAPI,
    entity_linking_api: RealEntityLinkingAPI,
    query_rewrite_api: RealQueryRewriteAPI,
    search_api: RealHybridSearchAPI,
    ranking_api: RealRankingAPI,
) -> dict:
    print(f"Running {name}...")
    stats: list[QueryStats] = []
    results: dict[str, list[dict]] = {}
    per_query = []
    for qid, query in queries.items():
        total_start = time.perf_counter()
        ctx = FlowContext(
            query,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
        )
        execution_start = time.perf_counter()
        result = executor(qid, ctx)
        raw_execution_ms = (time.perf_counter() - execution_start) * 1000
        generation_ms = float(result.get("_additional_generation_ms", 0.0))
        execution_ms = float(result.get("_execution_only_ms", raw_execution_ms))
        latency_ms = generation_ms + execution_ms
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
                "top_doc_ids": [hit.doc_id for hit in hits],
                "top_titles": [hit.title for hit in hits],
                "relevant_doc_ids": relevant_doc_ids(qrels[qid]),
                "query_metrics": evaluate_query_at_ks(qrels[qid], hard_negatives.get(qid, set()), [hit.doc_id for hit in hits], metrics_k),
                "stats": asdict(query_stats),
                "trace": ctx.trace[:18],
            }
        )
    metrics = evaluate_results(qrels, hard_negatives, results, metrics_k)
    latency = summarize_stats(stats)
    print(f"{name}: recall@{max(metrics_k)}={metrics[f'recall@{max(metrics_k)}']}, total={latency['mean_latency_ms']:.1f}ms, gen={latency['mean_generation_ms']:.1f}ms")
    return {
        "definition": SYSTEM_DEFINITIONS[name],
        "metrics": metrics,
        "latency": latency,
        "per_query": per_query,
    }


def run_real_fixed_flow_llm_qr(ctx: FlowContext, decision: dict, *, candidate_k: int, top_k: int) -> dict:
    generation_ms = float(decision.get("latency_ms", 0.0))
    subqueries = unique_runtime([ctx.query] + decision.get("rewrites", [])[:3])
    candidate_by_id: dict[str, SearchCandidate] = {}
    for subquery in subqueries:
        hits = ctx.search.search(subquery, mode="hybrid", top_k=candidate_k, bm25_weight=0.55)
        merge_runtime_candidates(candidate_by_id, hits)
    candidates = sorted(candidate_by_id.values(), key=lambda hit: hit.score, reverse=True)
    ctx.candidate_pool = len(candidates)
    ranked = ctx.ranking.rerank(ctx.query, candidates[:candidate_k], top_k=top_k)
    ctx.log(
        "real_fixed_flow_llm_qr",
        {
            "rewrites": decision.get("rewrites", []),
            "rationale": decision.get("rationale", ""),
            "candidate_pool": len(candidates),
            "rerank_candidates": min(len(candidates), candidate_k),
            "cache_hit": decision.get("cache_hit"),
        },
    )
    return {"hits": ranked, "candidates": candidates, "_additional_generation_ms": generation_ms}


def run_real_preset_flow_llm_router(ctx: FlowContext, decision: dict, *, candidate_k: int, top_k: int) -> dict:
    generation_ms = float(decision.get("latency_ms", 0.0))
    stacks = normalize_stacks(decision.get("preset_stacks", []), fallback=route_preset_stacks(ctx.query, allow_multiple=False))[:1]
    candidates = execute_preset_stacks(ctx, ctx.query, stacks, candidate_k=candidate_k)
    ctx.candidate_pool = len(candidates)
    ranked = ctx.ranking.rerank(ctx.query, candidates[:candidate_k], top_k=top_k)
    ctx.log(
        "real_preset_flow_llm_router",
        {
            "stacks": stacks,
            "rationale": decision.get("rationale", ""),
            "candidate_pool": len(candidates),
            "rerank_candidates": min(len(candidates), candidate_k),
            "cache_hit": decision.get("cache_hit"),
        },
    )
    return {"hits": ranked, "candidates": candidates, "_additional_generation_ms": generation_ms}


def run_real_agentic_fixed_flow_llm_reflection(
    ctx: FlowContext,
    decision: dict,
    decider: LLMDecisionGenerator,
    *,
    tool_candidate_k: int,
    final_candidate_k: int,
    top_k: int,
    max_reflection_rounds: int,
) -> dict:
    generation_ms = float(decision.get("latency_ms", 0.0))
    candidate_by_id: dict[str, SearchCandidate] = {}
    tool_calls = []
    reflection_rounds = []
    confident_doc_ids: list[str] = []
    queries = unique_runtime(decision.get("decomposed_queries", [])[:3] or [ctx.query])
    for query in queries:
        hits = call_fixed_flow_without_extra_llm(ctx, query, candidate_k=tool_candidate_k, top_k=max(top_k * 2, 20))
        tool_calls.append({"query": query, "returned": len(hits)})
        merge_runtime_candidates(candidate_by_id, hits)

    used_queries = set(queries)
    for round_index in range(max_reflection_rounds):
        candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
        observation = build_observation(
            ctx,
            candidates,
            tool_calls=tool_calls,
            mode="fixed_flow",
            decision=decision,
            round_index=round_index + 1,
        )
        reflection = decider.reflection(ctx.query, observation, mode="fixed_flow")
        generation_ms += float(reflection.get("latency_ms", 0.0))
        confident_doc_ids = unique_runtime(confident_doc_ids + reflection.get("confident_doc_ids", []))
        followup_queries = [
            query
            for query in unique_runtime(reflection.get("followup_queries", [])[:3])
            if query not in used_queries
        ]
        reflection_rounds.append(
            {
                "round": round_index + 1,
                "reflection": reflection,
                "followup_queries": followup_queries,
                "candidate_pool_before": len(candidates),
            }
        )
        if not reflection.get("needs_followup") or not followup_queries:
            break
        for query in followup_queries:
            hits = call_fixed_flow_without_extra_llm(ctx, query, candidate_k=tool_candidate_k, top_k=max(top_k * 2, 20))
            used_queries.add(query)
            tool_calls.append({"query": query, "returned": len(hits), "followup": True, "round": round_index + 1})
            merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    ctx.candidate_pool = len(candidates)
    final_hits, rerank_pool, finalizer = finalize_agentic_hits(
        ctx,
        candidates,
        final_candidate_k=final_candidate_k,
        top_k=top_k,
        confident_doc_ids=confident_doc_ids,
    )
    ctx.log(
        "real_agentic_fixed_flow_llm_reflection",
        {
            "initial_queries": queries,
            "tool_calls": tool_calls,
            "reflection_rounds": reflection_rounds,
            "candidate_pool": len(candidates),
            "finalizer": finalizer,
            "rerank_candidates": len(rerank_pool),
        },
    )
    return {"hits": final_hits, "candidates": candidates, "_additional_generation_ms": generation_ms}


def run_real_agentic_preset_flow_llm_reflection(
    ctx: FlowContext,
    decision: dict,
    decider: LLMDecisionGenerator,
    *,
    tool_candidate_k: int,
    final_candidate_k: int,
    top_k: int,
    max_reflection_rounds: int,
) -> dict:
    generation_ms = float(decision.get("latency_ms", 0.0))
    stacks = normalize_stacks(decision.get("preset_stacks", []), fallback=route_preset_stacks(ctx.query, allow_multiple=True))[:3]
    used_stacks = set()
    candidate_by_id: dict[str, SearchCandidate] = {}
    stack_calls = []
    reflection_rounds = []
    confident_doc_ids: list[str] = []
    for stack in stacks:
        hits = execute_preset_stack(ctx, ctx.query, stack, candidate_k=tool_candidate_k)
        used_stacks.add(stack)
        stack_calls.append({"stack": stack, "returned": len(hits)})
        merge_runtime_candidates(candidate_by_id, hits)

    for round_index in range(max_reflection_rounds):
        candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
        observation = build_observation(
            ctx,
            candidates,
            tool_calls=stack_calls,
            mode="preset_flow",
            decision=decision,
            round_index=round_index + 1,
        )
        reflection = decider.reflection(ctx.query, observation, mode="preset_flow")
        generation_ms += float(reflection.get("latency_ms", 0.0))
        confident_doc_ids = unique_runtime(confident_doc_ids + reflection.get("confident_doc_ids", []))
        followup_stacks = [
            stack
            for stack in normalize_stacks(reflection.get("followup_stacks", []), fallback=[])
            if stack not in used_stacks
        ][:3]
        reflection_rounds.append(
            {
                "round": round_index + 1,
                "reflection": reflection,
                "followup_stacks": followup_stacks,
                "candidate_pool_before": len(candidates),
            }
        )
        if not reflection.get("needs_followup") or not followup_stacks:
            break
        for stack in followup_stacks:
            hits = execute_preset_stack(ctx, ctx.query, stack, candidate_k=tool_candidate_k)
            used_stacks.add(stack)
            stack_calls.append({"stack": stack, "returned": len(hits), "followup": True, "round": round_index + 1})
            merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    ctx.candidate_pool = len(candidates)
    final_hits, rerank_pool, finalizer = finalize_agentic_hits(
        ctx,
        candidates,
        final_candidate_k=final_candidate_k,
        top_k=top_k,
        confident_doc_ids=confident_doc_ids,
    )
    ctx.log(
        "real_agentic_preset_flow_llm_reflection",
        {
            "initial_stacks": stacks,
            "stack_calls": stack_calls,
            "reflection_rounds": reflection_rounds,
            "candidate_pool": len(candidates),
            "finalizer": finalizer,
            "rerank_candidates": len(rerank_pool),
        },
    )
    return {"hits": final_hits, "candidates": candidates, "_additional_generation_ms": generation_ms}


def run_real_one_shot_codegen(ctx: FlowContext, generator: LLMSearchCodeGenerator, *, top_k: int, candidate_k: int, benchmark_hint: str) -> dict:
    generated = generator.generate(ctx.query, top_k=top_k, candidate_k=candidate_k, benchmark_hint=benchmark_hint)
    result = execute_real_code_with_repair(generated.code, ctx, generator, top_k=top_k, candidate_k=candidate_k, benchmark_hint=benchmark_hint)
    result["_additional_generation_ms"] = float(result.get("_additional_generation_ms", 0.0)) + generated.latency_ms
    return result


def run_real_agentic_codegen(ctx: FlowContext, generator: LLMSearchCodeGenerator, *, top_k: int, candidate_k: int, benchmark_hint: str) -> dict:
    generated = generator.generate(
        ctx.query,
        top_k=top_k,
        candidate_k=candidate_k,
        benchmark_hint=f"{benchmark_hint}; agentic mode with post-execution reflection",
    )
    result = execute_real_agentic_code(generated.code, ctx, generator, top_k=top_k, candidate_k=candidate_k, benchmark_hint=benchmark_hint)
    result["_additional_generation_ms"] = float(result.get("_additional_generation_ms", 0.0)) + generated.latency_ms
    return result


def call_fixed_flow_without_extra_llm(ctx: FlowContext, query: str, *, candidate_k: int, top_k: int) -> list[SearchCandidate]:
    hits = ctx.search.search(query, mode="hybrid", top_k=candidate_k, bm25_weight=0.55)
    rerank_top_k = min(candidate_k, max(top_k, 50))
    ranked = ctx.ranking.rerank(query, hits[:candidate_k], top_k=rerank_top_k)
    ranked_ids = {hit.doc_id for hit in ranked}
    merged = ranked + [hit for hit in hits if hit.doc_id not in ranked_ids]
    ctx.log(
        "fixed_flow_tool_call_no_extra_llm",
        {"query": query, "candidate_pool": len(hits), "reranked": len(ranked), "returned": len(merged)},
    )
    return merged


def finalize_agentic_hits(
    ctx: FlowContext,
    candidates: list[SearchCandidate],
    *,
    final_candidate_k: int,
    top_k: int,
    confident_doc_ids: list[str] | None = None,
) -> tuple[list[SearchCandidate], list[SearchCandidate], dict]:
    strategy = build_iterative_agentic_strategy(
        ctx.query,
        top_k=top_k,
        branch_top_k=min(final_candidate_k, 400),
        max_rerank_candidates=final_candidate_k,
    )
    by_id = {hit.doc_id: hit for hit in candidates}
    protected = [
        by_id[doc_id]
        for doc_id in (confident_doc_ids or [])
        if doc_id in by_id and authority_score(by_id[doc_id]) > 0
    ]
    if is_policy_query(ctx.query):
        policy_docs = [
            hit
            for hit in candidates
            if str((hit.metadata or {}).get("doc_type", "")).lower() == "policy"
        ]
        authority_docs = [
            hit
            for hit in candidates
            if str((hit.metadata or {}).get("doc_type", "")).lower() == "authority_matrix"
        ]
        policy_docs.sort(key=authority_score, reverse=True)
        authority_docs.sort(key=authority_score, reverse=True)
        protected = unique_candidates(protected + policy_docs[:2] + authority_docs[:2])
    goal_preselected = preselect_goal_evidence(
        candidates,
        strategy["goals"],
        max_preselected=min(top_k, 8),
    )
    rerank_pool = unique_candidates(protected + goal_preselected + candidates)[:final_candidate_k]
    ranked = ctx.ranking.rerank(ctx.query, rerank_pool, top_k=max(top_k * 5, 50))
    final_hits = authority_aware_topk(ranked, candidates, strategy["goals"], top_k)
    final_hits = protect_confident_hits(final_hits, protected, top_k=top_k)
    finalizer = {
        "goals": [goal["name"] for goal in strategy["goals"]],
        "protected_doc_ids": [hit.doc_id for hit in protected],
        "goal_preselected_doc_ids": [hit.doc_id for hit in goal_preselected],
        "rerank_candidates": len(rerank_pool),
    }
    return final_hits, rerank_pool, finalizer


def is_policy_query(query: str) -> bool:
    lower = query.lower()
    return any(term in lower for term in ["policy", "latency", "metric", "readout", "reflection", "candidate", "codegen", "follow-up code"])


def protect_confident_hits(
    final_hits: list[SearchCandidate],
    protected: list[SearchCandidate],
    *,
    top_k: int,
) -> list[SearchCandidate]:
    if not protected:
        return final_hits[:top_k]
    selected: list[SearchCandidate] = []
    selected_ids = set()
    for hit in protected:
        if hit.doc_id not in selected_ids:
            selected.append(hit)
            selected_ids.add(hit.doc_id)
        if len(selected) >= min(4, top_k):
            break
    for hit in final_hits:
        if hit.doc_id not in selected_ids:
            selected.append(hit)
            selected_ids.add(hit.doc_id)
        if len(selected) >= top_k:
            break
    return selected[:top_k]


def unique_candidates(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
    seen = set()
    result = []
    for hit in candidates:
        if hit.doc_id in seen:
            continue
        seen.add(hit.doc_id)
        result.append(hit)
    return result


def build_observation(
    ctx: FlowContext,
    candidates: list[SearchCandidate],
    *,
    tool_calls: list[dict],
    mode: str,
    decision: dict | None = None,
    round_index: int = 1,
) -> dict:
    top = candidates[:12]
    by_authority = sorted(candidates, key=authority_score, reverse=True)[:12]
    doc_type_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for hit in candidates[:200]:
        metadata = hit.metadata or {}
        doc_type = str(metadata.get("doc_type", "unknown"))
        source = str(metadata.get("source", "unknown"))
        doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1
        source_counts[source] = source_counts.get(source, 0) + 1
    return {
        "mode": mode,
        "query": ctx.query,
        "round": round_index,
        "planned_evidence_goals": (decision or {}).get("evidence_goals", []),
        "stop_requirements": (decision or {}).get("stop_requirements", []),
        "must_preserve_terms": (decision or {}).get("must_preserve_terms", []),
        "tool_calls": tool_calls,
        "candidate_pool": len(candidates),
        "top_doc_ids": [hit.doc_id for hit in top],
        "top_hits": [hit.compact(220) for hit in top[:8]],
        "authority_order_doc_ids": [hit.doc_id for hit in by_authority],
        "authority_hits": [hit.compact(180) for hit in by_authority[:8]],
        "doc_type_counts": sorted(doc_type_counts.items(), key=lambda item: item[1], reverse=True)[:12],
        "source_counts": sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:12],
        "available_followup_stacks": STACKS,
        "evidence_categories_to_check": [
            "alias registry",
            "account or escalation",
            "security ticket",
            "vendor advisory",
            "release note",
            "approval ledger/source authority",
            "policy",
            "negative evidence",
        ],
    }


def build_initial_decision_prompt(query: str, *, analysis: dict, category: str, difficulty: str) -> str:
    return textwrap.dedent(
        f"""
        You are controlling enterprise retrieval tools for agentic search. Return JSON only.

        Query:
        {query}

        Task metadata:
        - category: {category}
        - difficulty: {difficulty}

        Query analysis:
        {json.dumps(analysis, indent=2)[:5000]}

        Available preset search stacks:
        - general_hybrid: broad hybrid retrieval
        - alias_resolution: alias registry and source-of-truth name expansion
        - exact_security: CVE/SEC/version/vendor advisory/security ticket/release retrieval
        - wide_fanout: customer/account/escalation/war-room fanout
        - negative_evidence: explicit no/not/exclude/rejected evidence
        - authority: approval ledger/final/source-of-truth evidence
        - policy: policy, metrics, latency, required evaluation rules
        - semantic_multihop: dense/hybrid retrieval for long semantic or multi-hop evidence

        Planning rules:
        - Identify the evidence facets needed to answer, not just keywords.
        - Preserve exact IDs, aliases, versions, product names, customer names, and negation terms.
        - Choose routes that can retrieve all facets: exact identifiers, customer/account impact, release/advisory/ticket evidence, source authority, policy, and negative evidence.
        - For hard/multi-hop queries, decompose into subqueries that can be independently checked.
        - Stop conditions must be evidence-based. A large candidate pool alone is not enough if a required evidence type is missing.

        Return:
        - rewrites: 1-3 concise retrieval rewrites for a fixed multi-query hybrid search.
        - preset_stacks: 1-3 stacks to run initially.
        - decomposed_queries: 1-3 subqueries for an agent that can repeatedly call fixed search.
        - evidence_goals: the evidence categories that must be present before stopping.
        - stop_requirements: concrete proof conditions for stopping.
        - must_preserve_terms: exact terms that must survive rewrite/decomposition.
        - preferred_search_style: exact, semantic, authority, wide_fanout, policy, or mixed.
        - rationale: short reason.

        Be specific and conservative.
        """
    ).strip()


def build_reflection_prompt(query: str, observation: dict, *, mode: str) -> str:
    return textwrap.dedent(
        f"""
        You are reflecting on enterprise retrieval results. Return JSON only.

        Original query:
        {query}

        Retrieval mode:
        {mode}

        Observation:
        {json.dumps(observation, indent=2, default=str)[:9000]}

        Decide whether enough evidence is present. If not:
        - name the missing evidence goals.
        - for fixed_flow mode, return concrete followup_queries that target missing evidence and preserve exact terms.
        - for preset_flow mode, return followup_stacks from the available stack list.
        - protect confident_doc_ids that already look authoritative or directly relevant.

        Stop only if observed docs cover the planned evidence goals and stop requirements.
        If top hits are mostly distractors/decoys, or if release/advisory/account/approval/policy evidence is missing, continue.
        Do not over-search once all required evidence is present; preserve good evidence instead of letting follow-up noise bury it.
        Do not use ground-truth labels. Infer only from query, observed titles, metadata, snippets, and tool calls.
        """
    ).strip()


def sanitize_decision_payload(payload: dict) -> dict:
    if "preset_stacks" in payload:
        payload["preset_stacks"] = normalize_stacks(payload.get("preset_stacks", []), fallback=["general_hybrid"])
    if "followup_stacks" in payload:
        payload["followup_stacks"] = normalize_stacks(payload.get("followup_stacks", []), fallback=[])
    for key in [
        "rewrites",
        "decomposed_queries",
        "evidence_goals",
        "stop_requirements",
        "must_preserve_terms",
        "followup_queries",
        "covered_evidence_goals",
        "missing_evidence_goals",
        "confident_doc_ids",
    ]:
        if key in payload:
            payload[key] = clean_string_list(payload.get(key, []), limit=4)
    return payload


def normalize_initial_decision(decision: dict, *, fallback_query: str) -> dict:
    decision["rewrites"] = clean_string_list(decision.get("rewrites", []), limit=3)
    decision["preset_stacks"] = normalize_stacks(decision.get("preset_stacks", []), fallback=route_preset_stacks(fallback_query, allow_multiple=True))[:3]
    decision["decomposed_queries"] = clean_string_list(decision.get("decomposed_queries", []), limit=3) or [fallback_query]
    decision["evidence_goals"] = clean_string_list(decision.get("evidence_goals", []), limit=8)
    decision["stop_requirements"] = clean_string_list(decision.get("stop_requirements", []), limit=6)
    decision["must_preserve_terms"] = clean_string_list(decision.get("must_preserve_terms", []), limit=8)
    if decision.get("preferred_search_style") not in {"exact", "semantic", "authority", "wide_fanout", "policy", "mixed"}:
        decision["preferred_search_style"] = "mixed"
    return decision


def clean_string_list(items: Any, *, limit: int) -> list[str]:
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        text = " ".join(str(item).split())
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
        if len(result) >= limit:
            break
    return result


def normalize_stacks(items: Any, *, fallback: list[str]) -> list[str]:
    if not isinstance(items, list):
        items = []
    result = []
    seen = set()
    for item in items:
        stack = str(item).strip()
        if stack in STACKS and stack not in seen:
            result.append(stack)
            seen.add(stack)
    return result or list(fallback)


def build_summary_rows(systems: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    rows = []
    for name, result in systems.items():
        metrics = result["metrics"]
        latency = result["latency"]
        rows.append(
            {
                "system": name,
                f"recall@{k}": metrics[f"recall@{k}"],
                "mean_latency_ms": latency["mean_latency_ms"],
                "mean_generation_ms": latency["mean_generation_ms"],
                "mean_execution_ms": latency["mean_execution_ms"],
                "mean_search_calls": latency["mean_search_calls"],
                "mean_query_rewrite_calls": latency["mean_query_rewrite_calls"],
                "mean_rerank_pairs": latency["mean_rerank_pairs"],
                "definition": result["definition"],
            }
        )
    return sorted(rows, key=lambda row: (row[f"recall@{k}"], -row["mean_latency_ms"]), reverse=True)


def load_rule_comparison(path: str, task_ids: list[str], *, k: int) -> list[dict]:
    source = Path(path)
    if not source.exists():
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = []
    wanted = set(task_ids)
    for name, result in payload.get("systems", {}).items():
        values = [
            row["query_metrics"][f"recall@{k}"]
            for row in result.get("per_query", [])
            if row["qid"] in wanted
        ]
        if not values:
            continue
        latency = result.get("latency", {})
        rows.append(
            {
                "system": name,
                f"subset_recall@{k}": round(sum(values) / len(values), 4),
                "full_recall@10": result.get("metrics", {}).get(f"recall@{k}"),
                "full_mean_latency_ms": latency.get("mean_latency_ms"),
                "note": "existing rule-backed full-matrix run; subset recall recomputed on selected qids",
            }
        )
    return sorted(rows, key=lambda row: row[f"subset_recall@{k}"], reverse=True)


def build_per_query_comparison(systems: dict, task_by_id: dict, qrels: dict, ks: list[int]) -> list[dict]:
    k = max(ks)
    rows = []
    per_system = {name: {row["qid"]: row for row in result["per_query"]} for name, result in systems.items()}
    for qid, task in task_by_id.items():
        rows.append(
            {
                "qid": qid,
                "query": task["query"],
                "category": task["category"],
                "relevant_doc_ids": relevant_doc_ids(qrels[qid]),
                "systems": {
                    name: {
                        f"recall@{k}": system_rows[qid]["query_metrics"][f"recall@{k}"],
                        "top_doc_ids": system_rows[qid]["top_doc_ids"],
                    }
                    for name, system_rows in per_system.items()
                    if qid in system_rows
                },
            }
        )
    return rows


def render_report(output: dict) -> str:
    k = max(output["metrics_k"])
    lines = [
        "# Real LLM Search-as-Code Matrix",
        "",
        "## Setup",
        "",
        f"- Dataset: `{output['dataset']}` / split `{output['split']}`",
        f"- Tasks: `{', '.join(output['task_ids'])}`",
        f"- Candidate budget: `{output['candidate_k']}`",
        f"- Provider: `{output['provider']}` / model `{output['model'] or 'codex default'}`",
        f"- Metric: `Recall@{k}`",
        "",
        "## Real LLM Results",
        "",
        f"| System | Recall@{k} | Total ms | LLM ms | Exec ms | Search calls | QR calls | Rerank pairs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in output["summary_rows"]:
        lines.append(
            f"| `{row['system']}` | {row[f'recall@{k}']:.4f} | {row['mean_latency_ms']:.1f} | "
            f"{row['mean_generation_ms']:.1f} | {row['mean_execution_ms']:.1f} | "
            f"{row['mean_search_calls']:.2f} | {row['mean_query_rewrite_calls']:.2f} | {row['mean_rerank_pairs']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Compared With Existing Rule-Backed Matrix",
            "",
            "This uses the already-completed `experiment_matrix_results.json`. The subset recall is recomputed on the same selected qids; full-run latency is from the full 31-query run.",
            "",
            f"| Rule-backed system | Subset Recall@{k} | Full Recall@{k} | Full total ms |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in output["rule_matrix_subset"]:
        lines.append(
            f"| `{row['system']}` | {row[f'subset_recall@{k}']:.4f} | "
            f"{row.get('full_recall@10', 0):.4f} | {row.get('full_mean_latency_ms', 0):.1f} |"
        )

    lines.extend(["", "## Readout", ""])
    real = {row["system"]: row for row in output["summary_rows"]}
    rules = {row["system"]: row for row in output["rule_matrix_subset"]}
    if "real_agentic_code_gen" in real:
        lines.append(
            f"- Real agentic codegen reaches Recall@{k} `{real['real_agentic_code_gen'][f'recall@{k}']:.4f}` with "
            f"`{real['real_agentic_code_gen']['mean_generation_ms']:.1f}` ms/query spent in LLM generation/reflection."
        )
    if "real_agentic_preset_flow_llm_reflection" in real:
        lines.append(
            f"- Real agentic preset flow reaches Recall@{k} `{real['real_agentic_preset_flow_llm_reflection'][f'recall@{k}']:.4f}`; "
            "this tests whether model reflection can choose useful follow-up stacks without writing code."
        )
    if "agentic_code_gen_rule_reflection" in rules:
        rule_recall = rules["agentic_code_gen_rule_reflection"][f"subset_recall@{k}"]
        if "real_agentic_code_gen" in real and real["real_agentic_code_gen"][f"recall@{k}"] >= rule_recall:
            lines.append(
                f"- Real LLM agentic codegen now exceeds the existing rule-backed subset (`{real['real_agentic_code_gen'][f'recall@{k}']:.4f}` vs `{rule_recall:.4f}`), "
                "but at much higher LLM generation latency."
            )
        else:
            lines.append(
                f"- Existing rule-backed agentic codegen subset Recall@{k} is `{rule_recall:.4f}`. "
                "The gap to real LLM codegen is a direct reliability target."
            )

    lines.extend(["", "## Per-Query", ""])
    for row in output["per_query_comparison"]:
        lines.extend(
            [
                f"### {row['qid']}",
                "",
                row["query"],
                "",
                f"Relevant docs: `{', '.join(row['relevant_doc_ids'])}`",
                "",
                f"| System | Recall@{k} | Top docs |",
                "|---|---:|---|",
            ]
        )
        for name, system in row["systems"].items():
            lines.append(f"| `{name}` | {system[f'recall@{k}']:.4f} | `{', '.join(system['top_doc_ids'][:5])}` |")
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
