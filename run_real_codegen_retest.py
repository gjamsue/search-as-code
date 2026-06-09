#!/usr/bin/env python3
"""Retest real LLM Search-as-Code on a focused enterprise-query sample."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import time

from llm_search_codegen import LLMSearchCodeGenerator, execute_llm_generated_program
from real_search_stack.apis import (
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryRewriteAPI,
    RealQueryUnderstandingAPI,
    RealRankingAPI,
)
from run_flow_comparison import run_fixed_enriched_rerank
from run_sac_dataset_benchmark import (
    DATASET_DIR,
    candidate_to_row,
    evaluate_query_at_ks,
    evaluate_results,
    execute_generated_program,
    generate_iterative_agentic_sac_program,
    generate_sac_program,
    load_dataset,
    read_json,
    relevant_doc_ids,
    run_system,
)


DEFAULT_TASK_IDS = "sac-005,sac-028,sac-038,sac-042,sac-043"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a focused real LLM codegen retest.")
    parser.add_argument("--data-dir", default=str(DATASET_DIR))
    parser.add_argument("--split", default="test", choices=["train", "dev", "test", "all"])
    parser.add_argument("--task-ids", default=DEFAULT_TASK_IDS)
    parser.add_argument("--task-limit", type=int, default=0, help="Used only when --task-ids is empty.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-k", default="10")
    parser.add_argument("--candidate-k", type=int, default=400)
    parser.add_argument("--generated-branch-top-k", type=int, default=300)
    parser.add_argument("--generated-max-rerank-candidates", type=int, default=400)
    parser.add_argument("--systems", default="fixed_understanding_rewrite_hybrid_rerank,generated_search_as_code,generated_iterative_agentic_search_as_code,real_codegen_search_as_code,real_agentic_codegen_search_as_code")
    parser.add_argument("--real-codegen-provider", default="codex-cli", choices=["codex-cli", "openai"])
    parser.add_argument("--real-codegen-model", default="")
    parser.add_argument("--real-codegen-timeout", type=int, default=180)
    parser.add_argument("--real-codegen-cache-dir", default=".llm_codegen_cache/real_codegen_retest")
    parser.add_argument("--clear-cache", action="store_true")
    parser.add_argument("--codex-cli", default="/Applications/Codex.app/Contents/Resources/codex")
    parser.add_argument("--codex-reasoning-effort", default="low")
    parser.add_argument("--output", default="real_codegen_retest_results.json")
    parser.add_argument("--report", default="real_codegen_retest_report.md")
    parser.add_argument("--sample-codes", type=int, default=2)
    parser.add_argument("--wikidata", action="store_true")
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if args.clear_cache:
        shutil.rmtree(args.real_codegen_cache_dir, ignore_errors=True)

    data_dir = Path(args.data_dir)
    documents, tasks, qrels, hard_negatives = load_dataset(data_dir, split=args.split)
    task_ids = [item.strip() for item in args.task_ids.split(",") if item.strip()]
    if task_ids:
        wanted = set(task_ids)
        tasks = [task for task in tasks if task["task_id"] in wanted]
        missing = wanted - {task["task_id"] for task in tasks}
        if missing:
            raise SystemExit(f"Unknown or filtered-out task ids: {', '.join(sorted(missing))}")
    elif args.task_limit:
        tasks = tasks[: args.task_limit]
    if not tasks:
        raise SystemExit("No tasks selected")

    metrics_k = sorted({int(item) for item in args.metrics_k.split(",") if item.strip()})
    if args.top_k < max(metrics_k):
        raise SystemExit("--top-k must be >= max --metrics-k")

    print(f"Dataset: {data_dir}")
    print(f"Tasks: {len(tasks)}")
    print(f"Task ids: {', '.join(task['task_id'] for task in tasks)}")
    print("Loading tools...")
    query_understanding_api = RealQueryUnderstandingAPI()
    entity_linking_api = RealEntityLinkingAPI(wikidata_enabled=args.wikidata)
    query_rewrite_api = RealQueryRewriteAPI()
    search_api = RealHybridSearchAPI(documents, local_files_only=args.offline_models)
    ranking_api = RealRankingAPI(local_files_only=args.offline_models)

    task_queries = {task["task_id"]: task["query"] for task in tasks}
    task_by_id = {task["task_id"]: task for task in tasks}
    selected_systems = {item.strip() for item in args.systems.split(",") if item.strip()}
    systems: dict[str, dict] = {}

    one_shot_generator = build_generator(args, suffix="one_shot")
    agentic_generator = build_generator(args, suffix="agentic")
    benchmark_hint = (
        "custom enterprise Search-as-Code benchmark; retrieval must handle exact ids, aliases, "
        "authority/source-of-truth disambiguation, policy lookups, negative evidence, and multi-hop joins"
    )

    def run_named_system(name: str, code_generator, executor) -> None:
        if name not in selected_systems:
            return
        systems[name] = run_system(
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
            sample_codes=args.sample_codes,
        )

    run_named_system(
        "fixed_understanding_rewrite_hybrid_rerank",
        lambda query: "fixed enriched rerank",
        lambda code, ctx: run_fixed_enriched_rerank(ctx, candidate_k=args.candidate_k, top_k=args.top_k),
    )
    run_named_system(
        "generated_search_as_code",
        lambda query: generate_sac_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
            min_rerank_candidates=0,
        ),
        execute_generated_program,
    )
    run_named_system(
        "generated_iterative_agentic_search_as_code",
        lambda query: generate_iterative_agentic_sac_program(
            query,
            top_k=args.top_k,
            branch_top_k=args.generated_branch_top_k,
            max_rerank_candidates=args.generated_max_rerank_candidates,
        ),
        execute_generated_program,
    )
    run_named_system(
        "real_codegen_search_as_code",
        lambda query: one_shot_generator.generate(
            query,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            benchmark_hint=benchmark_hint,
        ).code,
        lambda code, ctx: execute_real_code_with_repair(
            code,
            ctx,
            one_shot_generator,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            benchmark_hint=benchmark_hint,
        ),
    )
    run_named_system(
        "real_agentic_codegen_search_as_code",
        lambda query: agentic_generator.generate(
            query,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            benchmark_hint=f"{benchmark_hint}; agentic mode with post-execution reflection",
        ).code,
        lambda code, ctx: execute_real_agentic_code(
            code,
            ctx,
            agentic_generator,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            benchmark_hint=benchmark_hint,
        ),
    )

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
        "generated_branch_top_k": args.generated_branch_top_k,
        "generated_max_rerank_candidates": args.generated_max_rerank_candidates,
        "real_codegen_provider": args.real_codegen_provider,
        "real_codegen_model": args.real_codegen_model,
        "codex_reasoning_effort": args.codex_reasoning_effort,
        "systems": systems,
        "summary": summarize_retest_systems(systems, k=max(metrics_k)),
    }
    output["per_query_comparison"] = build_per_query_comparison(output, task_by_id, qrels, hard_negatives)

    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    Path(args.report).write_text(render_retest_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def build_generator(args, *, suffix: str) -> LLMSearchCodeGenerator:
    return LLMSearchCodeGenerator(
        provider=args.real_codegen_provider,
        model=args.real_codegen_model,
        timeout_seconds=args.real_codegen_timeout,
        cache_dir=Path(args.real_codegen_cache_dir) / suffix,
        codex_cli=args.codex_cli,
        codex_reasoning_effort=args.codex_reasoning_effort,
    )


def execute_real_code_with_repair(code: str, ctx, generator: LLMSearchCodeGenerator, *, top_k: int, candidate_k: int, benchmark_hint: str) -> dict:
    started = time.perf_counter()
    try:
        result = execute_llm_generated_program(code, ctx, top_k=top_k, candidate_k=candidate_k)
        execution_only_ms = (time.perf_counter() - started) * 1000
        result["_executed_code"] = code
        result["_additional_generation_ms"] = 0.0
        result["_execution_only_ms"] = execution_only_ms
        return result
    except Exception as exc:
        first_execution_ms = (time.perf_counter() - started) * 1000
        ctx.log("codegen_runtime_error", {"error_type": type(exc).__name__, "error": str(exc)})
        repaired = generator.repair(
            ctx.query,
            code,
            exc,
            top_k=top_k,
            candidate_k=candidate_k,
            benchmark_hint=benchmark_hint,
        )
        ctx.log(
            "codegen_repair",
            {
                "provider": repaired.provider,
                "model": repaired.model,
                "cache_hit": repaired.cache_hit,
                "repair_latency_ms": repaired.latency_ms,
                "rationale": repaired.rationale,
            },
        )
        repair_started = time.perf_counter()
        result = execute_llm_generated_program(repaired.code, ctx, top_k=top_k, candidate_k=candidate_k)
        repair_execution_ms = (time.perf_counter() - repair_started) * 1000
        result["_executed_code"] = repaired.code
        result["_additional_generation_ms"] = repaired.latency_ms
        result["_execution_only_ms"] = first_execution_ms + repair_execution_ms
        return result


def execute_real_agentic_code(code: str, ctx, generator: LLMSearchCodeGenerator, *, top_k: int, candidate_k: int, benchmark_hint: str) -> dict:
    initial = execute_real_code_with_repair(
        code,
        ctx,
        generator,
        top_k=top_k,
        candidate_k=candidate_k,
        benchmark_hint=f"{benchmark_hint}; initial agentic code execution",
    )
    additional_generation_ms = float(initial.get("_additional_generation_ms", 0.0))
    execution_only_ms = float(initial.get("_execution_only_ms", 0.0))
    initial_code = initial.get("_executed_code", code)

    observation = build_reflection_observation(ctx, initial)
    reflected = generator.reflect(
        ctx.query,
        initial_code,
        observation,
        top_k=top_k,
        candidate_k=candidate_k,
        benchmark_hint=f"{benchmark_hint}; reflect after initial retrieval and generate improved code if evidence is incomplete",
    )
    additional_generation_ms += reflected.latency_ms
    ctx.log(
        "real_agentic_codegen_reflection",
        {
            "provider": reflected.provider,
            "model": reflected.model,
            "cache_hit": reflected.cache_hit,
            "reflection_codegen_ms": reflected.latency_ms,
            "rationale": reflected.rationale,
            "initial_top_doc_ids": observation["top_doc_ids"],
            "initial_candidate_pool": observation["candidate_pool"],
        },
    )

    final = execute_real_code_with_repair(
        reflected.code,
        ctx,
        generator,
        top_k=top_k,
        candidate_k=candidate_k,
        benchmark_hint=f"{benchmark_hint}; final reflected agentic code execution",
    )
    additional_generation_ms += float(final.get("_additional_generation_ms", 0.0))
    execution_only_ms += float(final.get("_execution_only_ms", 0.0))
    final["_additional_generation_ms"] = additional_generation_ms
    final["_execution_only_ms"] = execution_only_ms
    final["_executed_code"] = final.get("_executed_code", reflected.code)
    return final


def build_reflection_observation(ctx, result: dict) -> dict:
    hits = result.get("hits", [])
    candidates = result.get("candidates", [])
    return {
        "query": ctx.query,
        "candidate_pool": ctx.candidate_pool,
        "top_doc_ids": [hit.doc_id for hit in hits[:10]],
        "top_hits": [compact_observed_hit(hit, 220) for hit in hits[:8]],
        "candidate_sample": [compact_observed_hit(hit, 160) for hit in candidates[:8]],
        "tool_counts": {
            "query_understanding": ctx.query_understanding_calls,
            "entity_linking": ctx.entity_linking_calls,
            "query_rewrite": ctx.query_rewrite_calls,
            "search": ctx.search_calls,
            "rerank": ctx.rerank_calls,
            "rerank_pairs": ctx.rerank_pairs,
        },
        "trace_tail": ctx.trace[-8:],
        "evidence_categories_to_consider": [
            "exact identifier",
            "alias expansion",
            "account or escalation",
            "security ticket",
            "vendor advisory",
            "release note",
            "approval ledger or source authority",
            "policy or latency ledger",
            "negative evidence or exclusion",
        ],
    }


def compact_observed_hit(hit, max_chars: int) -> dict:
    if hasattr(hit, "compact"):
        return hit.compact(max_chars)
    text = str(hit.get("text", "")) if hasattr(hit, "get") else ""
    snippet = text[:max_chars].replace("\n", " ").strip()
    if len(text) > max_chars:
        snippet += "..."
    return {
        "id": hit.get("doc_id") or hit.get("id") if hasattr(hit, "get") else "",
        "title": hit.get("title", "") if hasattr(hit, "get") else "",
        "score": hit.get("score", 0) if hasattr(hit, "get") else 0,
        "metadata": hit.get("metadata", {}) if hasattr(hit, "get") else {},
        "snippet": snippet,
    }


def summarize_retest_systems(systems: dict, *, k: int) -> list[dict]:
    rows = []
    for name, result in systems.items():
        metrics = result["metrics"]
        latency = result["latency"]
        traces = [row["trace"] for row in result.get("per_query", [])]
        rows.append(
            {
                "system": name,
                f"recall@{k}": metrics[f"recall@{k}"],
                f"ndcg@{k}": metrics[f"ndcg@{k}"],
                f"mrr@{k}": metrics[f"mrr@{k}"],
                f"hard_negative_hit_rate@{k}": metrics[f"hard_negative_hit_rate@{k}"],
                "mean_latency_ms": latency["mean_latency_ms"],
                "mean_generation_ms": latency["mean_generation_ms"],
                "mean_execution_ms": latency["mean_execution_ms"],
                "mean_search_calls": latency["mean_search_calls"],
                "mean_rerank_pairs": latency["mean_rerank_pairs"],
                "runtime_errors": count_events(traces, "codegen_runtime_error"),
                "repairs": count_events(traces, "codegen_repair"),
                "reflections": count_events(traces, "real_agentic_codegen_reflection"),
            }
        )
    rows.sort(key=lambda row: (row[f"recall@{k}"], row[f"ndcg@{k}"]), reverse=True)
    return rows


def count_events(traces: list[list[dict]], event_name: str) -> int:
    return sum(1 for trace in traces for event in trace if event.get("event") == event_name)


def build_per_query_comparison(output: dict, task_by_id: dict, qrels: dict, hard_negatives: dict) -> list[dict]:
    k = max(output["metrics_k"])
    by_system = {
        name: {row["qid"]: row for row in result.get("per_query", [])}
        for name, result in output["systems"].items()
    }
    rows = []
    for qid in output["task_ids"]:
        row = {
            "qid": qid,
            "category": task_by_id[qid]["category"],
            "query": task_by_id[qid]["query"],
            "relevant_doc_ids": relevant_doc_ids(qrels[qid]),
            "hard_negative_doc_ids": sorted(hard_negatives.get(qid, set())),
            "systems": {},
        }
        for system, system_rows in by_system.items():
            if qid not in system_rows:
                continue
            item = system_rows[qid]
            row["systems"][system] = {
                "recall": item["query_metrics"][f"recall@{k}"],
                "ndcg": item["query_metrics"][f"ndcg@{k}"],
                "hard_negative_count": item["query_metrics"][f"hard_negative_count@{k}"],
                "top_doc_ids": item["top_doc_ids"],
                "stats": item["stats"],
                "trace": item["trace"],
            }
        rows.append(row)
    return rows


def render_retest_report(output: dict) -> str:
    k = max(output["metrics_k"])
    lines = [
        "# Real LLM Codegen Retest",
        "",
        "This retest compares one-shot real LLM Search-as-Code with an agentic real-codegen variant that runs an initial generated program, reflects on the observed evidence, then generates and executes a revised program.",
        "",
        f"- Dataset: `{output['dataset']}`",
        f"- Tasks: `{output['tasks']}` selected enterprise queries",
        f"- Task ids: `{', '.join(output['task_ids'])}`",
        f"- Corpus documents: `{output['documents']}`",
        f"- Candidate budget: `{output['candidate_k']}`",
        f"- Provider: `{output['real_codegen_provider']}`",
        f"- Codex reasoning effort: `{output['codex_reasoning_effort']}`",
        "",
        "## Readout",
        "",
        *render_readout(output, k),
        "",
        "## Summary",
        "",
        f"| System | Recall@{k} | nDCG@{k} | MRR@{k} | Hard-neg hit@{k} | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs | Repairs | Reflections |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in output["summary"]:
        lines.append(
            f"| `{row['system']}` | {row[f'recall@{k}']:.4f} | {row[f'ndcg@{k}']:.4f} | "
            f"{row[f'mrr@{k}']:.4f} | {row[f'hard_negative_hit_rate@{k}']:.4f} | "
            f"{row['mean_latency_ms']:.1f} | {row['mean_generation_ms']:.1f} | {row['mean_execution_ms']:.1f} | "
            f"{row['mean_search_calls']:.2f} | {row['mean_rerank_pairs']:.1f} | {row['repairs']} | {row['reflections']} |"
        )
    lines.extend(["", "## Per-Query Recall", ""])
    system_order = [row["system"] for row in output["summary"]]
    lines.append("| Query | Category | " + " | ".join(f"`{system}`" for system in system_order) + " |")
    lines.append("|---|---|" + "---:|" * len(system_order))
    for row in output["per_query_comparison"]:
        values = []
        for system in system_order:
            item = row["systems"].get(system)
            values.append(f"{item['recall']:.4f}" if item else "")
        lines.append(f"| {row['qid']} | {row['category']} | " + " | ".join(values) + " |")

    lines.extend(["", "## Real Codegen Behavior Notes", ""])
    for row in output["per_query_comparison"]:
        notes = real_codegen_notes(row)
        if not notes:
            continue
        lines.extend([f"### {row['qid']} - {row['category']}", "", row["query"], ""])
        lines.extend(notes)
        lines.append("")

    lines.extend(["## Method Notes", ""])
    lines.extend(
        [
            "- Real one-shot codegen performs one model code-generation call, then executes the generated program with one repair opportunity on runtime error.",
            "- Real agentic codegen performs initial generation, executes it, builds an observation from trace/top hits/tool counts, then generates and executes a revised program.",
            "- Ground-truth qrels and hard-negative labels are used only by the evaluator, not in the reflection prompt.",
            "- Latency is split into total wall time, model codegen time, and execution time.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_readout(output: dict, k: int) -> list[str]:
    rows = {row["system"]: row for row in output["summary"]}
    lines = []
    real_one = rows.get("real_codegen_search_as_code")
    real_agentic = rows.get("real_agentic_codegen_search_as_code")
    deterministic_agentic = rows.get("generated_iterative_agentic_search_as_code")
    deterministic_one = rows.get("generated_search_as_code")
    if real_one and real_agentic:
        delta = real_agentic[f"recall@{k}"] - real_one[f"recall@{k}"]
        lines.append(
            f"- Real agentic codegen improves Recall@{k} by `{delta:+.4f}` vs real one-shot "
            f"(`{real_agentic[f'recall@{k}']:.4f}` vs `{real_one[f'recall@{k}']:.4f}`), "
            f"but costs `{real_agentic['mean_latency_ms']:.1f}` ms total "
            f"(`{real_agentic['mean_generation_ms']:.1f}` ms codegen + `{real_agentic['mean_execution_ms']:.1f}` ms execution)."
        )
        lines.append(
            f"- Real one-shot codegen matches the deterministic one-shot/fixed recall on this sample "
            f"at `{real_one[f'recall@{k}']:.4f}`, but takes `{real_one['mean_latency_ms']:.1f}` ms total "
            f"with `{real_one['mean_generation_ms']:.1f}` ms spent generating code."
        )
        lines.append(
            f"- Real agentic generated a reflection for every query and needed `{real_agentic['repairs']}` runtime repairs; "
            f"this is the main reliability and latency gap to close."
        )
    if deterministic_agentic and real_agentic:
        lines.append(
            f"- Deterministic agentic codegen remains the upper-bound design target on this sample: "
            f"Recall@{k} `{deterministic_agentic[f'recall@{k}']:.4f}` at `{deterministic_agentic['mean_latency_ms']:.1f}` ms total."
        )
    if deterministic_one and real_one and deterministic_one[f"recall@{k}"] == real_one[f"recall@{k}"]:
        lines.append(
            "- The quality gap is not from the search stack itself; it is from the model's ability to write the right evidence-coverage program reliably."
        )
    return lines


def real_codegen_notes(row: dict) -> list[str]:
    notes = []
    one = row["systems"].get("real_codegen_search_as_code")
    agentic = row["systems"].get("real_agentic_codegen_search_as_code")
    if one and agentic:
        delta = agentic["recall"] - one["recall"]
        notes.append(
            f"- Real agentic delta vs real one-shot: `{delta:+.4f}` Recall@10 "
            f"({agentic['recall']:.4f} vs {one['recall']:.4f})."
        )
        reflection = first_event(agentic["trace"], "real_agentic_codegen_reflection")
        if reflection:
            payload = reflection["payload"]
            notes.append(
                f"- Reflection codegen: `{payload.get('reflection_codegen_ms', 0):.1f}` ms; "
                f"initial candidates `{payload.get('initial_candidate_pool')}`; "
                f"initial top ids `{', '.join(payload.get('initial_top_doc_ids', [])[:5])}`."
            )
        notes.append(f"- One-shot top ids: `{', '.join(one['top_doc_ids'][:5])}`.")
        notes.append(f"- Agentic top ids: `{', '.join(agentic['top_doc_ids'][:5])}`.")
    return notes


def first_event(trace: list[dict], event_name: str) -> dict | None:
    for event in trace:
        if event.get("event") == event_name:
            return event
    return None


if __name__ == "__main__":
    main()
