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
    candidate_to_row,
    execute_preset_stack,
    execute_preset_stacks,
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
        "rationale": {"type": "string"},
    },
    "required": ["rewrites", "preset_stacks", "decomposed_queries", "evidence_goals", "rationale"],
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
        "rationale": {"type": "string"},
    },
    "required": ["needs_followup", "followup_queries", "followup_stacks", "rationale"],
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
                    "prompt_version": 1,
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
) -> dict:
    generation_ms = float(decision.get("latency_ms", 0.0))
    candidate_by_id: dict[str, SearchCandidate] = {}
    tool_calls = []
    queries = unique_runtime(decision.get("decomposed_queries", [])[:3] or [ctx.query])
    for query in queries:
        hits = call_fixed_flow_without_extra_llm(ctx, query, candidate_k=tool_candidate_k, top_k=max(top_k * 2, 20))
        tool_calls.append({"query": query, "returned": len(hits)})
        merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    observation = build_observation(ctx, candidates, tool_calls=tool_calls, mode="fixed_flow")
    reflection = decider.reflection(ctx.query, observation, mode="fixed_flow")
    generation_ms += float(reflection.get("latency_ms", 0.0))
    followup_queries = unique_runtime(reflection.get("followup_queries", [])[:3])
    if reflection.get("needs_followup"):
        for query in followup_queries:
            hits = call_fixed_flow_without_extra_llm(ctx, query, candidate_k=tool_candidate_k, top_k=max(top_k * 2, 20))
            tool_calls.append({"query": query, "returned": len(hits), "followup": True})
            merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    ctx.candidate_pool = len(candidates)
    ranked = ctx.ranking.rerank(ctx.query, candidates[:final_candidate_k], top_k=top_k)
    ctx.log(
        "real_agentic_fixed_flow_llm_reflection",
        {
            "initial_queries": queries,
            "tool_calls": tool_calls,
            "reflection": reflection,
            "candidate_pool": len(candidates),
            "rerank_candidates": min(len(candidates), final_candidate_k),
        },
    )
    return {"hits": ranked, "candidates": candidates, "_additional_generation_ms": generation_ms}


def run_real_agentic_preset_flow_llm_reflection(
    ctx: FlowContext,
    decision: dict,
    decider: LLMDecisionGenerator,
    *,
    tool_candidate_k: int,
    final_candidate_k: int,
    top_k: int,
) -> dict:
    generation_ms = float(decision.get("latency_ms", 0.0))
    stacks = normalize_stacks(decision.get("preset_stacks", []), fallback=route_preset_stacks(ctx.query, allow_multiple=True))[:3]
    used_stacks = set()
    candidate_by_id: dict[str, SearchCandidate] = {}
    stack_calls = []
    for stack in stacks:
        hits = execute_preset_stack(ctx, ctx.query, stack, candidate_k=tool_candidate_k)
        used_stacks.add(stack)
        stack_calls.append({"stack": stack, "returned": len(hits)})
        merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    observation = build_observation(ctx, candidates, tool_calls=stack_calls, mode="preset_flow")
    reflection = decider.reflection(ctx.query, observation, mode="preset_flow")
    generation_ms += float(reflection.get("latency_ms", 0.0))
    followup_stacks = [
        stack
        for stack in normalize_stacks(reflection.get("followup_stacks", []), fallback=[])
        if stack not in used_stacks
    ][:3]
    if reflection.get("needs_followup"):
        for stack in followup_stacks:
            hits = execute_preset_stack(ctx, ctx.query, stack, candidate_k=tool_candidate_k)
            used_stacks.add(stack)
            stack_calls.append({"stack": stack, "returned": len(hits), "followup": True})
            merge_runtime_candidates(candidate_by_id, hits)

    candidates = sorted(candidate_by_id.values(), key=authority_score, reverse=True)
    ctx.candidate_pool = len(candidates)
    ranked = ctx.ranking.rerank(ctx.query, candidates[:final_candidate_k], top_k=top_k)
    ctx.log(
        "real_agentic_preset_flow_llm_reflection",
        {
            "initial_stacks": stacks,
            "stack_calls": stack_calls,
            "reflection": reflection,
            "candidate_pool": len(candidates),
            "rerank_candidates": min(len(candidates), final_candidate_k),
        },
    )
    return {"hits": ranked, "candidates": candidates, "_additional_generation_ms": generation_ms}


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
    ranked = ctx.ranking.rerank(query, hits[:candidate_k], top_k=top_k)
    ctx.log("fixed_flow_tool_call_no_extra_llm", {"query": query, "candidate_pool": len(hits), "returned": len(ranked)})
    return ranked


def build_observation(ctx: FlowContext, candidates: list[SearchCandidate], *, tool_calls: list[dict], mode: str) -> dict:
    top = candidates[:10]
    return {
        "mode": mode,
        "query": ctx.query,
        "tool_calls": tool_calls,
        "candidate_pool": len(candidates),
        "top_doc_ids": [hit.doc_id for hit in top],
        "top_hits": [hit.compact(180) for hit in top[:6]],
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
        You are controlling enterprise retrieval tools. Return JSON only.

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

        Return:
        - rewrites: 1-3 concise retrieval rewrites for a fixed multi-query hybrid search.
        - preset_stacks: 1-3 stacks to run initially.
        - decomposed_queries: 1-3 subqueries for an agent that can repeatedly call fixed search.
        - evidence_goals: the evidence categories that must be present before stopping.
        - rationale: short reason.

        Be specific. Preserve exact IDs, product versions, customer names, and negation.
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
        - for fixed_flow mode, return followup_queries that target missing evidence.
        - for preset_flow mode, return followup_stacks from the available stack list.

        Stop if the top evidence already covers the likely answer categories.
        Do not use ground-truth labels. Infer only from query, observed titles, metadata, snippets, and tool calls.
        """
    ).strip()


def sanitize_decision_payload(payload: dict) -> dict:
    if "preset_stacks" in payload:
        payload["preset_stacks"] = normalize_stacks(payload.get("preset_stacks", []), fallback=["general_hybrid"])
    if "followup_stacks" in payload:
        payload["followup_stacks"] = normalize_stacks(payload.get("followup_stacks", []), fallback=[])
    for key in ["rewrites", "decomposed_queries", "evidence_goals", "followup_queries"]:
        if key in payload:
            payload[key] = clean_string_list(payload.get(key, []), limit=4)
    return payload


def normalize_initial_decision(decision: dict, *, fallback_query: str) -> dict:
    decision["rewrites"] = clean_string_list(decision.get("rewrites", []), limit=3)
    decision["preset_stacks"] = normalize_stacks(decision.get("preset_stacks", []), fallback=route_preset_stacks(fallback_query, allow_multiple=True))[:3]
    decision["decomposed_queries"] = clean_string_list(decision.get("decomposed_queries", []), limit=3) or [fallback_query]
    decision["evidence_goals"] = clean_string_list(decision.get("evidence_goals", []), limit=8)
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
        lines.append(
            f"- Existing rule-backed agentic codegen subset Recall@{k} is `{rules['agentic_code_gen_rule_reflection'][f'subset_recall@{k}']:.4f}`. "
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
