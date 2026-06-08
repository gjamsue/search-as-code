#!/usr/bin/env python3
"""Run a content-level audit for the Search-as-Code benchmark dataset."""

from __future__ import annotations

from collections import Counter
import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
ALLOWED_ROUTE_MODES = {"bm25", "dense", "hybrid"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    corpus = read_jsonl(DATA_DIR / "corpus.jsonl")
    tasks = read_jsonl(DATA_DIR / "tasks.jsonl")
    hard_negative_rows = read_jsonl(DATA_DIR / "hard_negatives.jsonl")
    report = audit(corpus, tasks, hard_negative_rows)

    if args.write_report:
        (DATA_DIR / "quality_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        raise SystemExit(1)


def audit(corpus: list[dict], tasks: list[dict], hard_negative_rows: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    doc_by_id = {doc["doc_id"]: doc for doc in corpus}
    doc_type_counts = Counter(doc["metadata"]["doc_type"] for doc in corpus)
    split_counts = Counter(task["split"] for task in tasks)
    category_counts = Counter(task["category"] for task in tasks)
    operation_counts = Counter(op for task in tasks for op in task["required_operations"])
    route_mode_counts = Counter(
        route["mode"] for task in tasks for route in task["expected_flow"]["ideal_search_routes"]
    )
    evidence_count_distribution = Counter(len(task["evidence_doc_ids"]) for task in tasks)
    hard_negative_count_distribution = Counter(len(task["hard_negative_doc_ids"]) for task in tasks)
    structured_distractors = sum(
        count for doc_type, count in doc_type_counts.items() if doc_type.endswith("_distractor")
    )

    for task in tasks:
        task_id = task["task_id"]
        evidence = set(task["evidence_doc_ids"])
        hard_negatives = set(task["hard_negative_doc_ids"])
        if not hard_negatives:
            errors.append(f"{task_id} has no hard negatives.")
        for doc_id in evidence | hard_negatives:
            if doc_id not in doc_by_id:
                errors.append(f"{task_id} references missing doc: {doc_id}")
        for doc_id in evidence:
            doc_type = doc_by_id[doc_id]["metadata"]["doc_type"]
            if doc_id.startswith("distractor-") or doc_type.endswith("_distractor"):
                errors.append(f"{task_id} uses structured distractor as positive evidence: {doc_id}")
        overlap = evidence & hard_negatives
        if overlap:
            errors.append(f"{task_id} has evidence/hard-negative overlap: {sorted(overlap)}")
        for route in task["expected_flow"]["ideal_search_routes"]:
            if route["mode"] not in ALLOWED_ROUTE_MODES:
                errors.append(f"{task_id} uses unsupported route mode: {route['mode']}")
            if not 1 <= int(route["top_k"]) <= 60:
                errors.append(f"{task_id} route top_k out of range: {route}")
        missing_fields = missing_answer_field_mentions(task)
        if missing_fields:
            warnings.append(f"{task_id} answer fields not literally present in gold answer: {missing_fields}")

    hard_negative_expected = {
        (task["task_id"], doc_id, task["split"])
        for task in tasks
        for doc_id in task["hard_negative_doc_ids"]
    }
    hard_negative_actual = {
        (row["task_id"], row["doc_id"], row["split"]) for row in hard_negative_rows
    }
    if hard_negative_expected != hard_negative_actual:
        errors.append(
            "hard_negatives.jsonl does not match task hard_negative_doc_ids: "
            f"missing={len(hard_negative_expected - hard_negative_actual)}, "
            f"extra={len(hard_negative_actual - hard_negative_expected)}"
        )

    qrels_summary = audit_qrels(tasks, errors)
    return {
        "documents": len(corpus),
        "tasks": len(tasks),
        "splits": dict(sorted(split_counts.items())),
        "categories": dict(sorted(category_counts.items())),
        "document_types": dict(sorted(doc_type_counts.items())),
        "structured_distractors": structured_distractors,
        "hard_negative_rows": len(hard_negative_rows),
        "tasks_with_hard_negatives": sum(1 for task in tasks if task["hard_negative_doc_ids"]),
        "reflection_tasks": sum(1 for task in tasks if task["expected_flow"]["should_reflect"]),
        "route_modes": dict(sorted(route_mode_counts.items())),
        "operation_coverage": dict(sorted(operation_counts.items())),
        "evidence_count_distribution": stringify_counter(evidence_count_distribution),
        "hard_negative_count_distribution": stringify_counter(hard_negative_count_distribution),
        "qrels": qrels_summary,
        "errors": errors,
        "warnings": warnings,
    }


def audit_qrels(tasks: list[dict], errors: list[str]) -> dict:
    by_task = {task["task_id"]: task for task in tasks}
    summary: dict[str, dict[str, int]] = {}
    for split in ["train", "dev", "test"]:
        path = DATA_DIR / "beir" / "qrels" / f"{split}.tsv"
        rows = read_tsv(path)
        non_positive = 0
        non_evidence = 0
        for row in rows:
            task = by_task.get(row["query-id"])
            score = int(row["score"])
            if score <= 0:
                non_positive += 1
            if task and row["corpus-id"] not in set(task["evidence_doc_ids"]):
                non_evidence += 1
        if non_positive:
            errors.append(f"{split} qrels contains {non_positive} non-positive rows.")
        if non_evidence:
            errors.append(f"{split} qrels contains {non_evidence} non-evidence rows.")
        summary[split] = {
            "rows": len(rows),
            "non_positive_rows": non_positive,
            "non_evidence_rows": non_evidence,
        }
    return summary


def missing_answer_field_mentions(task: dict) -> list[str]:
    answer = normalize(task["gold_answer"])
    missing: list[str] = []
    for value in flatten_values(task.get("answer_fields", {})):
        if isinstance(value, bool) or value is None:
            continue
        text = normalize(str(value))
        if len(text) < 3:
            continue
        if text not in answer:
            missing.append(str(value))
    return missing


def flatten_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        values: list[Any] = []
        for child in value.values():
            values.extend(flatten_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(flatten_values(child))
        return values
    return [value]


def normalize(value: str) -> str:
    return value.lower().replace("_", " ").replace("-", " ").replace("/", " ")


def stringify_counter(counter: Counter) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter)}


def read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:] if line]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    main()
