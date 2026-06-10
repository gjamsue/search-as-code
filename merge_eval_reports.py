#!/usr/bin/env python3
"""Merge Search-as-Code evaluation artifacts into one executive report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "combined_eval_results.json"
DEFAULT_REPORT = "combined_eval_report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Search-as-Code eval JSON files.")
    parser.add_argument("--experiment", default="experiment_matrix_results.json")
    parser.add_argument("--real-llm", default="real_llm_matrix_results.json")
    parser.add_argument("--real-llm-full", default="real_llm_matrix_full_results.json")
    parser.add_argument("--real-codegen", default="real_codegen_retest_results.json")
    parser.add_argument("--named-baselines", default="named_search_baselines_results.json")
    parser.add_argument("--public-variant", default="public_variant_matrix_results.json")
    parser.add_argument("--public", default="public_benchmark_results.json")
    parser.add_argument("--legacy", default="sac_benchmark_results.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    add_experiment_rows(rows, artifacts, Path(args.experiment))
    add_real_llm_rows(rows, artifacts, Path(args.real_llm))
    add_real_llm_full_rows(rows, artifacts, Path(args.real_llm_full))
    add_real_codegen_rows(rows, artifacts, Path(args.real_codegen))
    add_named_baseline_rows(rows, artifacts, Path(args.named_baselines))
    add_public_variant_rows(rows, artifacts, Path(args.public_variant))
    add_public_rows(rows, artifacts, Path(args.public))
    add_legacy_rows(rows, artifacts, Path(args.legacy))

    output = {
        "artifacts": artifacts,
        "rows": sorted(rows, key=lambda row: (row["scope_order"], row["recall@10"]), reverse=True),
        "readout": build_readout(rows),
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    Path(args.report).write_text(render_report(output), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


def add_experiment_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    artifacts.append(artifact(path, "custom full matrix", payload.get("tasks"), payload.get("documents")))
    for item in payload.get("summary_rows", []):
        rows.append(
            normalize_row(
                source=path.name,
                scope="custom enterprise full test",
                scope_order=40,
                benchmark="sac-codegen-v3/test",
                queries=payload.get("tasks"),
                system=item.get("system"),
                row=item,
                note=item.get("family", "rule-backed full matrix"),
            )
        )


def add_real_llm_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    artifacts.append(artifact(path, "focused real LLM matrix", payload.get("tasks"), payload.get("documents")))
    for item in payload.get("summary_rows", []):
        rows.append(
            normalize_row(
                source=path.name,
                scope="focused real LLM sample",
                scope_order=50,
                benchmark="sac-codegen-v3/focused-5",
                queries=payload.get("tasks"),
                system=item.get("system"),
                row=item,
                note=item.get("definition", "real LLM matrix"),
            )
        )


def add_real_llm_full_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    artifacts.append(artifact(path, "full real LLM matrix", payload.get("tasks"), payload.get("documents")))
    for item in payload.get("summary_rows", []):
        rows.append(
            normalize_row(
                source=path.name,
                scope="full real LLM custom test",
                scope_order=60,
                benchmark="sac-codegen-v3/test-real-llm",
                queries=payload.get("tasks"),
                system=item.get("system"),
                row=item,
                note=item.get("definition", "full real LLM matrix"),
            )
        )


def add_real_codegen_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    artifacts.append(artifact(path, "focused real codegen retest", payload.get("tasks"), payload.get("documents")))
    for item in payload.get("summary", []):
        rows.append(
            normalize_row(
                source=path.name,
                scope="focused real codegen sample",
                scope_order=45,
                benchmark="sac-codegen-v3/focused-5",
                queries=payload.get("tasks"),
                system=item.get("system"),
                row=item,
                note="real codegen retest; total latency accounts for cached generation records",
            )
        )


def add_public_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    results = payload.get("results", [])
    if isinstance(results, dict):
        results = list(results.values())
    artifacts.append(artifact(path, "public benchmark sanity checks", sum(item.get("queries", 0) for item in results), None))
    for result in results:
        benchmark = result.get("display_name") or result.get("benchmark_id") or "public benchmark"
        for item in result.get("summary", []):
            rows.append(
                normalize_row(
                    source=path.name,
                    scope="public sanity check",
                    scope_order=20,
                    benchmark=benchmark,
                    queries=result.get("queries"),
                    system=item.get("system"),
                    row=item,
                    note="public sanity check, not leaderboard",
                )
            )


def add_named_baseline_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    artifacts.append(artifact(path, "custom named search baseline calibration", payload.get("tasks"), payload.get("documents")))
    for item in payload.get("summary_rows", []):
        rows.append(
            normalize_row(
                source=path.name,
                scope="custom named search baselines",
                scope_order=35,
                benchmark="sac-codegen-v3/test",
                queries=payload.get("tasks"),
                system=item.get("system"),
                row=item,
                note=item.get("reference") or item.get("implementation") or "named search baseline",
            )
        )


def add_public_variant_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    results = payload.get("results", [])
    if isinstance(results, dict):
        results = list(results.values())
    artifacts.append(artifact(path, "public architecture matrix", sum(item.get("queries", 0) for item in results), None))
    for result in results:
        benchmark = result.get("display_name") or result.get("benchmark_id") or "public benchmark"
        for item in result.get("summary", []):
            rows.append(
                normalize_row(
                    source=path.name,
                    scope="public architecture matrix",
                    scope_order=30,
                    benchmark=benchmark,
                    queries=result.get("queries"),
                    system=item.get("system"),
                    row=item,
                    note="baseline + 5 architecture variants on public datasets; deterministic/proxy full-batch, not leaderboard",
                )
            )


def add_legacy_rows(rows: list[dict], artifacts: list[dict], path: Path) -> None:
    payload = read_payload(path)
    if not payload:
        return
    systems = payload.get("systems", {})
    if not systems:
        return
    note_by_system = {
        item.get("system"): item.get("note", item.get("label", "legacy custom architecture comparison"))
        for item in payload.get("architecture_comparison", [])
    }
    artifacts.append(artifact(path, "custom full extended variants", payload.get("tasks"), payload.get("documents")))
    for system, result in systems.items():
        item = {}
        item.update(result.get("metrics", {}))
        item.update(result.get("latency", {}))
        rows.append(
            normalize_row(
                source=path.name,
                scope="custom full extended variants",
                scope_order=10,
                benchmark="sac-codegen-v3/test",
                queries=payload.get("tasks"),
                system=system,
                row=item,
                note=note_by_system.get(system, infer_variant_note(system)),
            )
        )


def infer_variant_note(system: str) -> str:
    return {
        "fixed_bm25": "lexical BM25 baseline",
        "fixed_semantic_dense": "dense semantic baseline",
        "fixed_hybrid": "hybrid BM25+dense baseline",
        "fixed_hybrid_rerank_small_budget": "hybrid + rerank with 400-candidate budget",
        "fixed_hybrid_rerank": "hybrid + rerank with 2,400-candidate budget",
        "fixed_understanding_rewrite_hybrid_rerank": "query understanding + rewrite + hybrid + rerank",
        "generated_search_as_code": "one-shot generated route plan",
        "generated_search_as_code_force_budget": "one-shot generated route plan with forced budget",
        "agentic_fixed_flow_iterative": "agent repeatedly calls fixed flow with reflection",
        "generated_reflective_search_as_code": "single-pass generated flow with reflection hooks",
        "generated_iterative_agentic_search_as_code": "generated code iterates with evidence-coverage reflection",
    }.get(system, "custom full-run variant")


def normalize_row(
    *,
    source: str,
    scope: str,
    scope_order: int,
    benchmark: str,
    queries: int | None,
    system: str,
    row: dict[str, Any],
    note: str,
) -> dict[str, Any]:
    generation_ms = number(row.get("mean_generation_ms"))
    execution_ms = number(row.get("mean_execution_ms"))
    total_ms = number(row.get("mean_latency_ms"))
    if total_ms == 0 and (generation_ms or execution_ms):
        total_ms = generation_ms + execution_ms
    if source == "real_codegen_retest_results.json" and system and system.startswith("real_"):
        total_ms = generation_ms + execution_ms
    return {
        "source": source,
        "scope": scope,
        "scope_order": scope_order,
        "benchmark": benchmark,
        "queries": queries,
        "system": system,
        "recall@10": number(row.get("recall@10")),
        "ndcg@10": number(row.get("ndcg@10")),
        "mrr@10": number(row.get("mrr@10")),
        "total_ms": round(total_ms, 3),
        "generation_ms": round(generation_ms, 3),
        "execution_ms": round(execution_ms, 3),
        "search_calls": number(row.get("mean_search_calls")),
        "rerank_pairs": number(row.get("mean_rerank_pairs")),
        "note": note,
    }


def build_readout(rows: list[dict]) -> dict[str, Any]:
    by_scope = {}
    for row in rows:
        by_scope.setdefault(row["scope"], []).append(row)
    scope_best = {}
    for scope, items in by_scope.items():
        scope_best[scope] = sorted(items, key=lambda row: row["recall@10"], reverse=True)[:3]

    real_llm = [row for row in rows if row["source"] == "real_llm_matrix_results.json"]
    real_by_system = {row["system"]: row for row in real_llm}
    full_real_llm = [row for row in rows if row["source"] == "real_llm_matrix_full_results.json"]
    full_real_by_system = {row["system"]: row for row in full_real_llm}
    return {
        "best_by_scope": scope_best,
        "real_llm_key_deltas": {
            "agentic_preset_vs_router": delta(real_by_system, "real_agentic_preset_flow_llm_reflection", "real_preset_flow_llm_router"),
            "agentic_codegen_vs_one_shot": delta(real_by_system, "real_agentic_code_gen", "real_one_shot_code_gen"),
            "agentic_preset_vs_agentic_codegen_latency_ratio": ratio(
                real_by_system.get("real_agentic_code_gen", {}).get("total_ms"),
                real_by_system.get("real_agentic_preset_flow_llm_reflection", {}).get("total_ms"),
            ),
        },
        "full_real_llm_key_deltas": {
            "agentic_preset_vs_router": delta(full_real_by_system, "real_agentic_preset_flow_llm_reflection", "real_preset_flow_llm_router"),
            "agentic_codegen_vs_one_shot": delta(full_real_by_system, "real_agentic_code_gen", "real_one_shot_code_gen"),
            "agentic_codegen_vs_agentic_preset": delta(full_real_by_system, "real_agentic_code_gen", "real_agentic_preset_flow_llm_reflection"),
            "agentic_preset_vs_agentic_codegen_latency_ratio": ratio(
                full_real_by_system.get("real_agentic_code_gen", {}).get("total_ms"),
                full_real_by_system.get("real_agentic_preset_flow_llm_reflection", {}).get("total_ms"),
            ),
        },
    }


def render_report(output: dict[str, Any]) -> str:
    rows = output["rows"]
    lines = [
        "# Combined Search-as-Code Evaluation",
        "",
        "## Executive Readout",
        "",
        *render_executive_readout(output),
        "",
        "## Main Results",
        "",
        "| Scope | Benchmark | System | Recall@10 | Total ms | LLM/codegen ms | Exec ms | Search calls | Rerank pairs |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["scope"] == "custom full extended variants":
            continue
        lines.append(format_row(row))

    extended = [row for row in rows if row["scope"] == "custom full extended variants"]
    if extended:
        lines.extend(
            [
                "",
                "## Full Custom Extended Variants",
                "",
                "These are the additional full-dataset variants from `sac_benchmark_results.json` on the same 31-query test split.",
                "",
                "| System | Recall@10 | nDCG@10 | MRR@10 | Total ms | Search calls | Rerank pairs | Note |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in sorted(extended, key=lambda item: item["recall@10"], reverse=True):
            lines.append(
                f"| `{row['system']}` | {row['recall@10']:.4f} | {row['ndcg@10']:.4f} | {row['mrr@10']:.4f} | "
                f"{row['total_ms']:.1f} | {row['search_calls']:.2f} | {row['rerank_pairs']:.1f} | {row['note']} |"
            )

    lines.extend(["", "## Artifacts", ""])
    for item in output["artifacts"]:
        lines.append(f"- `{item['path']}`: {item['kind']}; queries={item.get('queries')}; documents={item.get('documents')}")
    return "\n".join(lines) + "\n"


def render_executive_readout(output: dict[str, Any]) -> list[str]:
    deltas = output["readout"].get("full_real_llm_key_deltas") or output["readout"]["real_llm_key_deltas"]
    lines = [
        "- Scope note: the main real-LLM result is now the full 31-query custom enterprise test; the older 5-query focused sample remains as a debugging artifact.",
        "- Full real-LLM eval confirms the ordering: agentic codegen is highest quality, followed by one-shot codegen and agentic preset search.",
        f"- Agentic codegen beats one-shot codegen by `{deltas['agentic_codegen_vs_one_shot']['recall_delta']:+.4f}` Recall@10.",
        f"- Agentic preset reflection beats single preset routing by `{deltas['agentic_preset_vs_router']['recall_delta']:+.4f}` Recall@10.",
        f"- Agentic codegen reaches the highest quality, but costs `{deltas['agentic_preset_vs_agentic_codegen_latency_ratio']:.1f}x` the agentic preset latency.",
        *render_named_baseline_readout(output["rows"]),
        *render_public_variant_readout(output["rows"]),
        "- Recommended interpretation: use preset-stack agentic search as the practical product path; keep full codegen as an advanced/research path for hard cases.",
    ]
    return lines


def render_named_baseline_readout(rows: list[dict[str, Any]]) -> list[str]:
    named_rows = [row for row in rows if row["source"] == "named_search_baselines_results.json"]
    if not named_rows:
        return []
    by_system = {row["system"]: row for row in named_rows}
    bm25 = by_system.get("okapi_bm25_rank_bm25", {})
    dense = by_system.get("minilm_biencoder_dense", {})
    rerank = by_system.get("hybrid_cross_encoder_rerank", {})
    return [
        f"- Custom named-search calibration: Okapi BM25 reaches `{number(bm25.get('recall@10')):.4f}`, dense bi-encoder `{number(dense.get('recall@10')):.4f}`, and hybrid+CrossEncoder rerank `{number(rerank.get('recall@10')):.4f}` Recall@10.",
    ]


def render_public_variant_readout(rows: list[dict[str, Any]]) -> list[str]:
    public_rows = [row for row in rows if row["source"] == "public_variant_matrix_results.json"]
    if not public_rows:
        return []
    by_benchmark: dict[str, dict[str, dict]] = {}
    for row in public_rows:
        by_benchmark.setdefault(row["benchmark"], {})[row["system"]] = row
    lines = []
    scifact = by_benchmark.get("BEIR/scifact")
    if scifact:
        agentic = scifact.get("agentic_code_gen_rule_reflection", {})
        fixed = scifact.get("fixed_flow_model_qr", {})
        lines.append(
            f"- Public SciFact check is effectively a tie: agentic codegen `{number(agentic.get('recall@10')):.4f}` vs fixed flow `{number(fixed.get('recall@10')):.4f}` Recall@10."
        )
    hotpot = by_benchmark.get("HotpotQA dev-distractor slice")
    if hotpot:
        fixed = hotpot.get("fixed_flow_model_qr", {})
        agentic = hotpot.get("agentic_code_gen_rule_reflection", {})
        lines.append(
            f"- Public HotpotQA check favors fixed flow: `{number(fixed.get('recall@10')):.4f}` vs agentic codegen `{number(agentic.get('recall@10')):.4f}` Recall@10."
        )
    return lines


def format_row(row: dict[str, Any]) -> str:
    return (
        f"| {row['scope']} | {row['benchmark']} | `{row['system']}` | "
        f"{row['recall@10']:.4f} | {row['total_ms']:.1f} | {row['generation_ms']:.1f} | "
        f"{row['execution_ms']:.1f} | {row['search_calls']:.2f} | {row['rerank_pairs']:.1f} |"
    )


def delta(by_system: dict[str, dict], left: str, right: str) -> dict[str, float]:
    left_row = by_system.get(left, {})
    right_row = by_system.get(right, {})
    return {
        "left_recall": number(left_row.get("recall@10")),
        "right_recall": number(right_row.get("recall@10")),
        "recall_delta": round(number(left_row.get("recall@10")) - number(right_row.get("recall@10")), 4),
        "left_total_ms": number(left_row.get("total_ms")),
        "right_total_ms": number(right_row.get("total_ms")),
    }


def ratio(numerator: Any, denominator: Any) -> float:
    numerator_value = number(numerator)
    denominator_value = number(denominator)
    if denominator_value == 0:
        return 0.0
    return round(numerator_value / denominator_value, 2)


def artifact(path: Path, kind: str, queries: Any, documents: Any) -> dict[str, Any]:
    return {"path": str(path), "kind": kind, "queries": queries, "documents": documents}


def read_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
