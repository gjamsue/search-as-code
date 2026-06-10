#!/usr/bin/env python3
"""Recompute cached retrieval metrics after qrels changes.

This does not rerun search, rerank, or LLM generation. It only re-scores stored
`top_doc_ids` against the current custom SAC dataset qrels.
"""

from __future__ import annotations

import json
from pathlib import Path

from run_sac_dataset_benchmark import (
    DATASET_DIR,
    build_architecture_comparison,
    build_comparisons,
    evaluate_query_at_ks,
    evaluate_results,
    load_dataset,
    relevant_doc_ids,
    render_report as render_sac_report,
    select_examples,
)


def main() -> None:
    _documents, tasks, qrels, hard_negatives = load_dataset(DATASET_DIR, split="test")
    task_by_id = {task["task_id"]: task for task in tasks}

    update_sac_benchmark(task_by_id, qrels, hard_negatives)
    update_experiment_matrix(task_by_id, qrels, hard_negatives)
    update_real_llm_matrix("real_llm_matrix_results.json", "real_llm_matrix_report.md", task_by_id, qrels, hard_negatives)
    update_real_llm_matrix(
        "real_llm_matrix_full_results.json",
        "real_llm_matrix_full_report.md",
        task_by_id,
        qrels,
        hard_negatives,
    )
    update_real_codegen_retest(task_by_id, qrels, hard_negatives)

    print("Recomputed cached custom metrics.")


def update_sac_benchmark(task_by_id: dict, qrels: dict, hard_negatives: dict) -> None:
    path = Path("sac_benchmark_results.json")
    if not path.exists():
        return
    output = read_json(path)
    update_system_metrics(output, qrels, hard_negatives)
    metrics_k = output["metrics_k"]
    output["comparisons"] = build_comparisons(output["systems"], metrics_k)
    output["architecture_comparison"] = build_architecture_comparison(output["systems"], metrics_k)
    output["selected_examples"] = select_examples(output["systems"], task_by_id, qrels, hard_negatives, metrics_k)
    write_json(path, output)
    Path("sac_benchmark_report.md").write_text(render_sac_report(output), encoding="utf-8")


def update_experiment_matrix(task_by_id: dict, qrels: dict, hard_negatives: dict) -> None:
    path = Path("experiment_matrix_results.json")
    if not path.exists():
        return
    from run_experiment_matrix import build_summary_rows, render_matrix_report, select_matrix_examples

    output = read_json(path)
    update_system_metrics(output, qrels, hard_negatives)
    output["summary_rows"] = build_summary_rows(output["systems"], output["metrics_k"])
    output["selected_examples"] = select_matrix_examples(output["systems"], task_by_id, qrels, output["metrics_k"])
    write_json(path, output)
    Path("experiment_matrix_report.md").write_text(render_matrix_report(output), encoding="utf-8")


def update_real_llm_matrix(filename: str, report_name: str, task_by_id: dict, qrels: dict, hard_negatives: dict) -> None:
    path = Path(filename)
    if not path.exists():
        return
    from run_real_llm_matrix import (
        build_per_query_comparison,
        build_summary_rows,
        load_rule_comparison,
        render_report,
    )

    output = read_json(path)
    update_system_metrics(output, qrels, hard_negatives)
    output["summary_rows"] = build_summary_rows(output["systems"], output["metrics_k"])
    output["per_query_comparison"] = build_per_query_comparison(output["systems"], task_by_id, qrels, output["metrics_k"])
    output["rule_matrix_subset"] = load_rule_comparison(
        "experiment_matrix_results.json",
        output["task_ids"],
        k=max(output["metrics_k"]),
    )
    write_json(path, output)
    Path(report_name).write_text(render_report(output), encoding="utf-8")


def update_real_codegen_retest(task_by_id: dict, qrels: dict, hard_negatives: dict) -> None:
    path = Path("real_codegen_retest_results.json")
    if not path.exists():
        return
    from run_real_codegen_retest import build_per_query_comparison, render_retest_report, summarize_retest_systems

    output = read_json(path)
    update_system_metrics(output, qrels, hard_negatives)
    output["summary"] = summarize_retest_systems(output["systems"], k=max(output["metrics_k"]))
    output["per_query_comparison"] = build_per_query_comparison(output, task_by_id, qrels, hard_negatives)
    write_json(path, output)
    Path("real_codegen_retest_report.md").write_text(render_retest_report(output), encoding="utf-8")


def update_system_metrics(output: dict, qrels: dict, hard_negatives: dict) -> None:
    metrics_k = output["metrics_k"]
    for result in output.get("systems", {}).values():
        per_query = result.get("per_query", [])
        if not per_query:
            continue
        ranked_by_qid = {
            row["qid"]: [{"doc_id": doc_id} for doc_id in row.get("top_doc_ids", [])]
            for row in per_query
        }
        result["metrics"] = evaluate_results(qrels, hard_negatives, ranked_by_qid, metrics_k)
        for row in per_query:
            qid = row["qid"]
            if qid not in qrels:
                continue
            top_doc_ids = row.get("top_doc_ids", [])
            row["relevant_doc_ids"] = relevant_doc_ids(qrels[qid])
            if "hard_negative_doc_ids" in row:
                row["hard_negative_doc_ids"] = sorted(hard_negatives.get(qid, set()))
            row["query_metrics"] = evaluate_query_at_ks(qrels[qid], hard_negatives.get(qid, set()), top_doc_ids, metrics_k)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
