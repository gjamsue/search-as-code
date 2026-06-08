#!/usr/bin/env python3
"""Validate the custom Search-as-Code benchmark dataset."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MIN_DOCUMENTS = 5000
MIN_STRUCTURED_DISTRACTORS = 4500
MIN_TASKS_WITH_HARD_NEGATIVES = 44
REQUIRED_DISTRACTOR_TYPES = {
    "account_brief_distractor",
    "escalation_distractor",
    "guide_distractor",
    "meeting_note_distractor",
    "release_distractor",
    "security_advisory_distractor",
    "security_ticket_distractor",
}


def main() -> None:
    corpus = read_jsonl(DATA_DIR / "corpus.jsonl")
    tasks = read_jsonl(DATA_DIR / "tasks.jsonl")
    hard_negative_rows = read_jsonl(DATA_DIR / "hard_negatives.jsonl")
    errors: list[str] = []

    doc_ids = [doc["doc_id"] for doc in corpus]
    task_ids = [task["task_id"] for task in tasks]
    doc_id_set = set(doc_ids)
    doc_by_id = {doc["doc_id"]: doc for doc in corpus}

    if len(doc_ids) != len(doc_id_set):
        errors.append("Duplicate document IDs found.")
    if len(task_ids) != len(set(task_ids)):
        errors.append("Duplicate task IDs found.")

    required_doc_keys = {"doc_id", "title", "text", "metadata"}
    required_task_keys = {
        "task_id",
        "split",
        "category",
        "difficulty",
        "query",
        "gold_answer",
        "answer_fields",
        "evidence_doc_ids",
        "hard_negative_doc_ids",
        "required_operations",
        "expected_flow",
        "evaluation",
    }
    for doc in corpus:
        missing = required_doc_keys - set(doc)
        if missing:
            errors.append(f"{doc.get('doc_id', '<unknown>')} missing doc keys: {sorted(missing)}")
        if len(doc.get("text", "")) < 80:
            errors.append(f"{doc.get('doc_id')} text is too short.")
        metadata = doc.get("metadata", {})
        for key in ["doc_type", "source"]:
            if key not in metadata:
                errors.append(f"{doc.get('doc_id')} missing metadata.{key}.")

    for task in tasks:
        task_id = task.get("task_id", "<unknown>")
        missing = required_task_keys - set(task)
        if missing:
            errors.append(f"{task_id} missing task keys: {sorted(missing)}")
        if len(task.get("query", "")) < 30:
            errors.append(f"{task_id} query is too short.")
        if len(task.get("gold_answer", "")) < 50:
            errors.append(f"{task_id} gold_answer is too short.")
        evidence = task.get("evidence_doc_ids", [])
        if len(evidence) < 2:
            errors.append(f"{task_id} has fewer than 2 evidence docs.")
        for doc_id in evidence:
            if doc_id not in doc_id_set:
                errors.append(f"{task_id} references missing evidence doc: {doc_id}")
                continue
            doc = doc_by_id[doc_id]
            doc_type = doc.get("metadata", {}).get("doc_type", "")
            if doc_id.startswith("distractor-") or doc_type.endswith("_distractor"):
                errors.append(f"{task_id} uses distractor doc as positive evidence: {doc_id}")
        for doc_id in task.get("hard_negative_doc_ids", []):
            if doc_id not in doc_id_set:
                errors.append(f"{task_id} references missing hard negative doc: {doc_id}")
        overlap = set(evidence) & set(task.get("hard_negative_doc_ids", []))
        if overlap:
            errors.append(f"{task_id} has docs in both evidence and hard negatives: {sorted(overlap)}")
        if not task.get("required_operations"):
            errors.append(f"{task_id} has no required operations.")
        routes = task.get("expected_flow", {}).get("ideal_search_routes", [])
        if not routes:
            errors.append(f"{task_id} has no ideal search routes.")
        for route in routes:
            if not {"query", "mode", "top_k"} <= set(route):
                errors.append(f"{task_id} route is missing query/mode/top_k: {route}")
        if task.get("split") not in {"train", "dev", "test"}:
            errors.append(f"{task_id} has invalid split {task.get('split')!r}.")

    split_counts = Counter(task["split"] for task in tasks)
    category_counts = Counter(task["category"] for task in tasks)
    operation_counts = Counter(op for task in tasks for op in task["required_operations"])
    doc_type_counts = Counter(doc["metadata"]["doc_type"] for doc in corpus)
    tasks_with_hard_negatives = sum(1 for task in tasks if task["hard_negative_doc_ids"])
    distractor_count = sum(
        count for doc_type, count in doc_type_counts.items() if doc_type.endswith("_distractor")
    )

    if len(corpus) < MIN_DOCUMENTS:
        errors.append(f"Expected at least {MIN_DOCUMENTS} documents.")
    if distractor_count < MIN_STRUCTURED_DISTRACTORS:
        errors.append(f"Expected at least {MIN_STRUCTURED_DISTRACTORS} structured distractor documents.")
    missing_distractor_types = REQUIRED_DISTRACTOR_TYPES - set(doc_type_counts)
    if missing_distractor_types:
        errors.append(f"Missing required distractor types: {sorted(missing_distractor_types)}")
    if tasks_with_hard_negatives < MIN_TASKS_WITH_HARD_NEGATIVES:
        errors.append(f"Expected at least {MIN_TASKS_WITH_HARD_NEGATIVES} tasks with hard negatives.")
    if split_counts["test"] < 18:
        errors.append("Expected at least 18 test tasks.")
    if len(category_counts) < 8:
        errors.append("Expected at least 8 task categories.")
    for op in [
        "fanout_search",
        "join",
        "metadata_filter",
        "bm25_exact",
        "evidence_reflection",
        "negative_evidence_check",
        "candidate_pruning",
    ]:
        if operation_counts[op] == 0:
            errors.append(f"Required operation {op!r} is not covered.")

    qrel_errors = validate_beir_qrels(tasks)
    errors.extend(qrel_errors)
    hard_negative_errors = validate_hard_negative_export(tasks, hard_negative_rows)
    errors.extend(hard_negative_errors)

    summary = {
        "documents": len(corpus),
        "tasks": len(tasks),
        "splits": dict(sorted(split_counts.items())),
        "categories": dict(sorted(category_counts.items())),
        "document_types": dict(sorted(doc_type_counts.items())),
        "structured_distractors": distractor_count,
        "tasks_with_hard_negatives": tasks_with_hard_negatives,
        "hard_negative_rows": len(hard_negative_rows),
        "top_operations": dict(operation_counts.most_common(12)),
        "reflection_tasks": sum(1 for task in tasks if task["expected_flow"]["should_reflect"]),
    }

    print(json.dumps(summary, indent=2, sort_keys=True))
    if errors:
        print("\nValidation errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print("\nValidation passed.")


def validate_beir_qrels(tasks: list[dict]) -> list[str]:
    errors: list[str] = []
    task_by_id = {task["task_id"]: task for task in tasks}
    qrels_dir = DATA_DIR / "beir" / "qrels"
    for split in ["train", "dev", "test"]:
        path = qrels_dir / f"{split}.tsv"
        if not path.exists():
            errors.append(f"Missing qrels file: {path}")
            continue
        seen_by_task: dict[str, set[str]] = defaultdict(set)
        with path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                task_id = row["query-id"]
                doc_id = row["corpus-id"]
                score = int(row["score"])
                if score <= 0:
                    errors.append(f"qrels contains non-positive score for {task_id}/{doc_id}: {score}")
                if task_id not in task_by_id:
                    errors.append(f"qrels references missing task: {task_id}")
                    continue
                seen_by_task[task_id].add(doc_id)
                if doc_id not in set(task_by_id[task_id]["evidence_doc_ids"]):
                    errors.append(f"qrels contains non-evidence doc for {task_id}: {doc_id}")
        for task in tasks:
            if task["split"] != split:
                continue
            missing = set(task["evidence_doc_ids"]) - seen_by_task.get(task["task_id"], set())
            if missing:
                errors.append(f"{task['task_id']} qrels missing evidence docs: {sorted(missing)}")
    return errors


def validate_hard_negative_export(tasks: list[dict], rows: list[dict]) -> list[str]:
    errors: list[str] = []
    expected = {
        (task["task_id"], doc_id, task["split"])
        for task in tasks
        for doc_id in task["hard_negative_doc_ids"]
    }
    actual = {(row["task_id"], row["doc_id"], row["split"]) for row in rows}
    if expected != actual:
        errors.append(
            f"hard_negatives.jsonl mismatch: missing={len(expected - actual)}, extra={len(actual - expected)}"
        )

    by_split: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        if row.get("score") != 0:
            errors.append(f"hard negative row must have score 0: {row}")
        by_split[row["split"]].add((row["task_id"], row["doc_id"]))

    export_dir = DATA_DIR / "beir" / "hard_negatives"
    for split in ["train", "dev", "test"]:
        path = export_dir / f"{split}.tsv"
        if not path.exists():
            errors.append(f"Missing hard negative export: {path}")
            continue
        seen: set[tuple[str, str]] = set()
        with path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                if int(row["score"]) != 0:
                    errors.append(f"hard negative export contains non-zero score: {row}")
                seen.add((row["query-id"], row["corpus-id"]))
        if seen != by_split.get(split, set()):
            errors.append(
                f"{split} hard negative export mismatch: missing={len(by_split.get(split, set()) - seen)}, extra={len(seen - by_split.get(split, set()))}"
            )
    return errors


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    main()
