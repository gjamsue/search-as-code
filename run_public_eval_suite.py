#!/usr/bin/env python3
"""Run the canonical reusable public eval suite.

This is a thin wrapper around run_public_benchmarks.py so future agentic-search
experiments can reuse the same public datasets, systems, and budgets without
copying a long command from the README.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


DEFAULT_BENCHMARKS = "beir/scifact,hotpotqa/distractor"
DEFAULT_SYSTEMS = (
    "fixed_flow_model_qr,preset_flow_model_router,agentic_fixed_flow_rule_reflection,"
    "agentic_preset_flows_rule_reflection,one_shot_code_gen_rule_policy,agentic_code_gen_rule_reflection"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Search-as-Code public eval suite.")
    parser.add_argument("--benchmarks", default=DEFAULT_BENCHMARKS)
    parser.add_argument("--hotpot-limit", type=int, default=100)
    parser.add_argument("--candidate-k", type=int, default=40)
    parser.add_argument("--fixed-small-candidate-k", type=int, default=40)
    parser.add_argument("--generated-branch-top-k", type=int, default=20)
    parser.add_argument("--generated-max-rerank-candidates", type=int, default=40)
    parser.add_argument("--systems", default=DEFAULT_SYSTEMS)
    parser.add_argument("--output", default="public_variant_matrix_results.json")
    parser.add_argument("--report", default="public_variant_matrix_report.md")
    parser.add_argument("--per-query", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--sample-codes", type=int, default=0)
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    command = [
        sys.executable,
        str(Path(__file__).with_name("run_public_benchmarks.py")),
        "--benchmarks",
        args.benchmarks,
        "--hotpot-limit",
        str(args.hotpot_limit),
        "--candidate-k",
        str(args.candidate_k),
        "--fixed-small-candidate-k",
        str(args.fixed_small_candidate_k),
        "--generated-branch-top-k",
        str(args.generated_branch_top_k),
        "--generated-max-rerank-candidates",
        str(args.generated_max_rerank_candidates),
        "--systems",
        args.systems,
        "--sample-codes",
        str(args.sample_codes),
        "--output",
        args.output,
        "--report",
        args.report,
    ]
    command.append("--per-query" if args.per_query else "--no-per-query")
    command.append("--offline-models" if args.offline_models else "--no-offline-models")
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
