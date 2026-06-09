#!/usr/bin/env python3
"""Run public benchmark sanity checks for Search-as-Code flows.

This runner complements the custom enterprise benchmark. It intentionally
separates two settings:

- BEIR small datasets, where full-corpus local indexing is feasible.
- HotpotQA dev-distractor slices, where we use official HotpotQA contexts but
  do not claim a fullwiki or BEIR leaderboard number.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
from urllib import request

from beir.datasets.data_loader import GenericDataLoader

from real_search_stack.apis import (
    IndexedDocument,
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryRewriteAPI,
    RealQueryUnderstandingAPI,
    RealRankingAPI,
)
from llm_search_codegen import LLMSearchCodeGenerator, execute_llm_generated_program
from run_flow_comparison import (
    execute_generated_program,
    execute_reflective_generated_program,
    fixed_enriched_rerank_code,
    fixed_rerank_code,
    fixed_search_code,
    generate_reflective_initial_program,
    generate_search_program,
    run_fixed_enriched_rerank,
    run_fixed_rerank,
    run_fixed_search,
    run_system,
)
from run_real_benchmark import BEIR_DATASETS, download_dataset


HOTPOTQA_DISTRACTOR_URLS = [
    "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json",
    "https://huggingface.co/datasets/namlh2004/hotpotqa/resolve/main/hotpot_dev_distractor_v1.json",
]


@dataclass
class LoadedBenchmark:
    benchmark_id: str
    display_name: str
    source_url: str
    setting: str
    split: str
    documents: list[IndexedDocument]
    queries: dict[str, str]
    qrels: dict[str, dict[str, int]]
    notes: list[str]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run public benchmark checks for Search-as-Code.")
    parser.add_argument(
        "--benchmarks",
        default="beir/scifact,hotpotqa/distractor",
        help="Comma-separated benchmarks. Supported: beir/scifact, beir/fiqa, beir/fever, beir/nq, hotpotqa/distractor.",
    )
    parser.add_argument("--split", default="test")
    parser.add_argument("--beir-query-limit", type=int, default=0, help="0 means all queries for BEIR datasets.")
    parser.add_argument("--hotpot-limit", type=int, default=160, help="Number of HotpotQA dev examples to pool.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=60)
    parser.add_argument("--fixed-small-candidate-k", type=int, default=32)
    parser.add_argument("--generated-branch-top-k", type=int, default=24)
    parser.add_argument("--generated-max-rerank-candidates", type=int, default=60)
    parser.add_argument("--generated-min-rerank-candidates", type=int, default=0)
    parser.add_argument(
        "--systems",
        default="fixed_bm25,fixed_hybrid_rerank,fixed_understanding_rewrite_hybrid_rerank,generated_search_as_code",
        help=(
            "Comma-separated systems. Supported: fixed_bm25, fixed_semantic_dense, fixed_hybrid, "
            "fixed_hybrid_rerank, fixed_understanding_rewrite_hybrid_rerank, generated_search_as_code, "
            "generated_reflective_search_as_code, real_codegen_search_as_code."
        ),
    )
    parser.add_argument("--real-codegen-provider", default="codex-cli", choices=["codex-cli", "openai"])
    parser.add_argument("--real-codegen-model", default="")
    parser.add_argument("--real-codegen-timeout", type=int, default=120)
    parser.add_argument("--real-codegen-cache-dir", default=".llm_codegen_cache")
    parser.add_argument("--codex-cli", default="/Applications/Codex.app/Contents/Resources/codex")
    parser.add_argument("--codex-reasoning-effort", default="low")
    parser.add_argument("--data-dir", default="benchmarks")
    parser.add_argument("--output", default="public_benchmark_results.json")
    parser.add_argument("--report", default="public_benchmark_report.md")
    parser.add_argument("--sample-codes", type=int, default=2)
    parser.add_argument("--per-query", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--wikidata", action="store_true")
    parser.add_argument("--offline-models", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if args.offline_models:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    data_dir = Path(args.data_dir)
    benchmark_ids = [item.strip() for item in args.benchmarks.split(",") if item.strip()]
    selected_systems = {item.strip() for item in args.systems.split(",") if item.strip()}
    results = []

    for benchmark_id in benchmark_ids:
        loaded = load_benchmark(
            benchmark_id,
            data_dir=data_dir,
            split=args.split,
            beir_query_limit=args.beir_query_limit,
            hotpot_limit=args.hotpot_limit,
        )
        print(f"\n=== {loaded.display_name} ===")
        print(f"Setting: {loaded.setting}")
        print(f"Documents: {len(loaded.documents)}")
        print(f"Queries: {len(loaded.queries)}")
        print("Loading tools...")
        query_understanding_api = RealQueryUnderstandingAPI()
        entity_linking_api = RealEntityLinkingAPI(wikidata_enabled=args.wikidata)
        query_rewrite_api = RealQueryRewriteAPI()
        search_api = RealHybridSearchAPI(loaded.documents, local_files_only=args.offline_models)
        ranking_api = RealRankingAPI(local_files_only=args.offline_models)

        started = time.perf_counter()
        systems = run_public_systems(
            loaded.queries,
            loaded.qrels,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            fixed_small_candidate_k=args.fixed_small_candidate_k,
            generated_branch_top_k=args.generated_branch_top_k,
            generated_max_rerank_candidates=args.generated_max_rerank_candidates,
            generated_min_rerank_candidates=args.generated_min_rerank_candidates,
            selected_systems=selected_systems,
            real_codegen_provider=args.real_codegen_provider,
            real_codegen_model=args.real_codegen_model,
            real_codegen_timeout=args.real_codegen_timeout,
            real_codegen_cache_dir=args.real_codegen_cache_dir,
            codex_cli=args.codex_cli,
            codex_reasoning_effort=args.codex_reasoning_effort,
            benchmark_hint=f"{loaded.display_name}: {loaded.setting}",
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=args.sample_codes,
            include_per_query=args.per_query,
        )
        results.append(
            {
                "benchmark_id": loaded.benchmark_id,
                "display_name": loaded.display_name,
                "source_url": loaded.source_url,
                "setting": loaded.setting,
                "split": loaded.split,
                "documents": len(loaded.documents),
                "queries": len(loaded.queries),
                "top_k": args.top_k,
                "candidate_k": args.candidate_k,
                "runtime_seconds": round(time.perf_counter() - started, 3),
                "notes": loaded.notes,
                "systems": systems,
                "summary": summarize_public_systems(systems, k=args.top_k),
            }
        )

    output = {
        "benchmarks": benchmark_ids,
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "fixed_small_candidate_k": args.fixed_small_candidate_k,
        "generated_branch_top_k": args.generated_branch_top_k,
        "generated_max_rerank_candidates": args.generated_max_rerank_candidates,
        "generated_min_rerank_candidates": args.generated_min_rerank_candidates,
        "systems": sorted(selected_systems),
        "real_codegen_provider": args.real_codegen_provider,
        "real_codegen_model": args.real_codegen_model,
        "wikidata_enabled": args.wikidata,
        "offline_models": args.offline_models,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    Path(args.report).write_text(render_public_report(output), encoding="utf-8")
    print(f"\nWrote {args.output}")
    print(f"Wrote {args.report}")


def load_benchmark(
    benchmark_id: str,
    *,
    data_dir: Path,
    split: str,
    beir_query_limit: int,
    hotpot_limit: int,
) -> LoadedBenchmark:
    if benchmark_id.startswith("beir/"):
        dataset = benchmark_id.split("/", 1)[1]
        return load_beir_dataset(dataset, data_dir=data_dir, split=split, query_limit=beir_query_limit)
    if benchmark_id == "hotpotqa/distractor":
        return load_hotpotqa_distractor(data_dir=data_dir, limit=hotpot_limit)
    raise SystemExit(f"Unsupported benchmark: {benchmark_id}")


def load_beir_dataset(dataset: str, *, data_dir: Path, split: str, query_limit: int) -> LoadedBenchmark:
    if dataset not in BEIR_DATASETS:
        raise SystemExit(f"Unsupported BEIR dataset: {dataset}")
    data_path = download_dataset(dataset, data_dir)
    corpus, queries, qrels = GenericDataLoader(data_path).load(split=split)
    if query_limit:
        selected_ids = list(queries)[:query_limit]
        queries = {qid: queries[qid] for qid in selected_ids}
        qrels = {qid: qrels[qid] for qid in selected_ids if qid in qrels}
    documents = [
        IndexedDocument(
            doc_id=doc_id,
            title=doc.get("title", ""),
            text=doc.get("text", ""),
            metadata={"benchmark": f"beir/{dataset}", "source": "beir"},
        )
        for doc_id, doc in corpus.items()
    ]
    return LoadedBenchmark(
        benchmark_id=f"beir/{dataset}",
        display_name=f"BEIR/{dataset}",
        source_url=BEIR_DATASETS[dataset],
        setting="Full BEIR corpus loaded locally",
        split=split,
        documents=documents,
        queries=queries,
        qrels=qrels,
        notes=[
            "This is a real BEIR dataset loaded through the BEIR GenericDataLoader.",
            "Metrics are local-system sanity-check numbers, not leaderboard submissions.",
        ],
    )


def load_hotpotqa_distractor(*, data_dir: Path, limit: int) -> LoadedBenchmark:
    path = download_hotpotqa_distractor(data_dir)
    examples = json.loads(path.read_text(encoding="utf-8"))[:limit]
    documents_by_id: dict[str, IndexedDocument] = {}
    queries: dict[str, str] = {}
    qrels: dict[str, dict[str, int]] = {}

    for index, example in enumerate(examples, start=1):
        qid = example.get("_id") or f"hotpot-{index:05d}"
        queries[qid] = example["question"]
        support_titles = {title for title, _sent_id in example.get("supporting_facts", [])}
        qrels[qid] = {}

        for title, sentences in example.get("context", []):
            text = " ".join(sentences)
            doc_id = hotpot_doc_id(title, text)
            documents_by_id.setdefault(
                doc_id,
                IndexedDocument(
                    doc_id=doc_id,
                    title=title,
                    text=text,
                    metadata={"benchmark": "hotpotqa/distractor", "source": "hotpotqa_context"},
                ),
            )
            if title in support_titles:
                qrels[qid][doc_id] = 1

    return LoadedBenchmark(
        benchmark_id="hotpotqa/distractor",
        display_name="HotpotQA dev-distractor slice",
        source_url=HOTPOTQA_DISTRACTOR_URLS[0],
        setting=f"Official dev-distractor contexts pooled across {len(examples)} examples",
        split="dev-distractor",
        documents=list(documents_by_id.values()),
        queries=queries,
        qrels=qrels,
        notes=[
            "Uses official HotpotQA dev-distractor examples and supporting-fact labels.",
            "Corpus is the pooled distractor context from selected examples, not HotpotQA fullwiki and not BEIR HotpotQA full corpus.",
            "Use this as a multi-hop public sanity check, not as a leaderboard number.",
        ],
    )


def download_hotpotqa_distractor(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "hotpotqa" / "hotpot_dev_distractor_v1.json"
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for url in HOTPOTQA_DISTRACTOR_URLS:
        try:
            print(f"Downloading HotpotQA dev-distractor from {url}")
            req = request.Request(url, headers={"User-Agent": "search-as-code-public-benchmark/0.1"})
            with request.urlopen(req, timeout=20) as response, target.open("wb") as handle:
                handle.write(response.read())
            return target
        except Exception as exc:
            last_error = exc
            if target.exists():
                target.unlink()
    raise RuntimeError(f"Could not download HotpotQA dev-distractor data: {last_error}")


def hotpot_doc_id(title: str, text: str) -> str:
    digest = hashlib.sha1((title + "\n" + text).encode("utf-8")).hexdigest()[:12]
    safe_title = "".join(ch.lower() if ch.isalnum() else "-" for ch in title)[:48].strip("-")
    return f"hotpot-{safe_title}-{digest}"


def run_public_systems(
    queries: dict,
    qrels: dict,
    *,
    top_k: int,
    candidate_k: int,
    fixed_small_candidate_k: int,
    generated_branch_top_k: int,
    generated_max_rerank_candidates: int,
    generated_min_rerank_candidates: int,
    selected_systems: set[str],
    real_codegen_provider: str,
    real_codegen_model: str,
    real_codegen_timeout: int,
    real_codegen_cache_dir: str,
    codex_cli: str,
    codex_reasoning_effort: str,
    benchmark_hint: str,
    query_understanding_api: RealQueryUnderstandingAPI,
    entity_linking_api: RealEntityLinkingAPI,
    query_rewrite_api: RealQueryRewriteAPI,
    search_api: RealHybridSearchAPI,
    ranking_api: RealRankingAPI,
    sample_codes: int,
    include_per_query: bool,
) -> dict:
    supported_systems = {
        "fixed_bm25",
        "fixed_semantic_dense",
        "fixed_hybrid",
        "fixed_hybrid_rerank",
        "fixed_understanding_rewrite_hybrid_rerank",
        "generated_search_as_code",
        "generated_reflective_search_as_code",
        "real_codegen_search_as_code",
    }
    unknown = selected_systems - supported_systems
    if unknown:
        raise SystemExit(f"Unsupported systems: {', '.join(sorted(unknown))}")

    systems = {}
    for mode, label in [
        ("bm25", "fixed_bm25"),
        ("dense", "fixed_semantic_dense"),
        ("hybrid", "fixed_hybrid"),
    ]:
        if label not in selected_systems:
            continue
        systems[label] = run_system(
            label,
            queries,
            qrels,
            top_k,
            lambda query, mode=mode: fixed_search_code(mode),
            lambda code, ctx, mode=mode: run_fixed_search(ctx, mode=mode, top_k=top_k),
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=0,
            include_per_query=include_per_query,
        )

    if "fixed_hybrid_rerank" in selected_systems:
        systems["fixed_hybrid_rerank"] = run_system(
            "fixed_hybrid_rerank",
            queries,
            qrels,
            top_k,
            lambda query: fixed_rerank_code(candidate_k),
            lambda code, ctx: run_fixed_rerank(ctx, candidate_k=candidate_k, top_k=top_k),
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=0,
            include_per_query=include_per_query,
        )

    if "fixed_understanding_rewrite_hybrid_rerank" in selected_systems:
        systems["fixed_understanding_rewrite_hybrid_rerank"] = run_system(
            "fixed_understanding_rewrite_hybrid_rerank",
            queries,
            qrels,
            top_k,
            lambda query: fixed_enriched_rerank_code(candidate_k),
            lambda code, ctx: run_fixed_enriched_rerank(ctx, candidate_k=candidate_k, top_k=top_k),
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=0,
            include_per_query=include_per_query,
        )

    if "generated_search_as_code" in selected_systems:
        systems["generated_search_as_code"] = run_system(
            "generated_search_as_code",
            queries,
            qrels,
            top_k,
            lambda query: generate_search_program(
                query,
                top_k=top_k,
                branch_top_k=generated_branch_top_k,
                max_rerank_candidates=generated_max_rerank_candidates,
                min_rerank_candidates=generated_min_rerank_candidates,
            ),
            execute_generated_program,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=sample_codes,
            include_per_query=include_per_query,
        )

    if "generated_reflective_search_as_code" in selected_systems:
        systems["generated_reflective_search_as_code"] = run_system(
            "generated_reflective_search_as_code",
            queries,
            qrels,
            top_k,
            lambda query: generate_reflective_initial_program(
                query,
                top_k=top_k,
                branch_top_k=generated_branch_top_k,
                max_rerank_candidates=generated_max_rerank_candidates,
            ),
            lambda code, ctx: execute_reflective_generated_program(
                code,
                ctx,
                top_k=top_k,
                max_rerank_candidates=generated_max_rerank_candidates,
            ),
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=sample_codes,
            include_per_query=include_per_query,
        )
    if "real_codegen_search_as_code" in selected_systems:
        llm_generator = LLMSearchCodeGenerator(
            provider=real_codegen_provider,
            model=real_codegen_model,
            timeout_seconds=real_codegen_timeout,
            cache_dir=real_codegen_cache_dir,
            codex_cli=codex_cli,
            codex_reasoning_effort=codex_reasoning_effort,
        )

        def generate_real_code(query: str) -> str:
            return llm_generator.generate(
                query,
                top_k=top_k,
                candidate_k=candidate_k,
                benchmark_hint=benchmark_hint,
            ).code

        def execute_real_code(code: str, ctx) -> dict:
            try:
                result = execute_llm_generated_program(code, ctx, top_k=top_k, candidate_k=candidate_k)
                result["_executed_code"] = code
                return result
            except Exception as exc:
                ctx.log("codegen_runtime_error", {"error_type": type(exc).__name__, "error": str(exc)})
                repaired = llm_generator.repair(
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
                result = execute_llm_generated_program(repaired.code, ctx, top_k=top_k, candidate_k=candidate_k)
                result["_executed_code"] = repaired.code
                return result

        systems["real_codegen_search_as_code"] = run_system(
            "real_codegen_search_as_code",
            queries,
            qrels,
            top_k,
            generate_real_code,
            execute_real_code,
            query_understanding_api=query_understanding_api,
            entity_linking_api=entity_linking_api,
            query_rewrite_api=query_rewrite_api,
            search_api=search_api,
            ranking_api=ranking_api,
            sample_codes=sample_codes,
            include_per_query=include_per_query,
        )
    return systems


def summarize_public_systems(systems: dict, *, k: int) -> list[dict]:
    rows = []
    for system, result in systems.items():
        metrics = result["metrics"]
        latency = result["latency"]
        rows.append(
            {
                "system": system,
                f"recall@{k}": metrics[f"recall@{k}"],
                f"ndcg@{k}": metrics[f"ndcg@{k}"],
                f"mrr@{k}": metrics[f"mrr@{k}"],
                "mean_latency_ms": latency["mean_latency_ms"],
                "mean_generation_ms": latency["mean_generation_ms"],
                "mean_execution_ms": latency["mean_execution_ms"],
                "mean_search_calls": latency["mean_search_calls"],
                "mean_rerank_pairs": latency["mean_rerank_pairs"],
            }
        )
    rows.sort(key=lambda row: (row[f"recall@{k}"], row[f"ndcg@{k}"]), reverse=True)
    return rows


def render_public_report(output: dict) -> str:
    k = output["top_k"]
    lines = [
        "# Public Benchmark Sanity Check",
        "",
        "These runs complement the custom enterprise Search-as-Code benchmark. They are intended to test whether the implementation behaves sensibly on known public datasets, not to claim official leaderboard numbers.",
        "",
        "Note: `generated_search_as_code` in this report is the deterministic Search-as-Code proxy used for reproducible full-batch evaluation. Use `real_codegen_search_as_code` for true model-generated Python; see `real_codegen_demo_report.md` for the current smoke test.",
        "",
        f"- Top-k: `{k}`",
        f"- Rerank candidate budget: `{output['candidate_k']}`",
        f"- Generated branch top-k: `{output['generated_branch_top_k']}`",
        f"- Generated max rerank candidates: `{output['generated_max_rerank_candidates']}`",
        "",
        "## Summary",
        "",
        f"| Benchmark | Setting | Docs | Queries | Best system by Recall@{k} | Recall@{k} | nDCG@{k} | MRR@{k} | Total ms | Codegen ms | Execution ms |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in output["results"]:
        summary_rows = result.get("summary", [])
        if summary_rows and "mean_generation_ms" not in summary_rows[0]:
            summary_rows = summarize_public_systems(result["systems"], k=k)
        best = summary_rows[0]
        lines.append(
            f"| {result['display_name']} | {result['setting']} | {result['documents']} | {result['queries']} | "
            f"`{best['system']}` | {best[f'recall@{k}']:.4f} | {best[f'ndcg@{k}']:.4f} | "
            f"{best[f'mrr@{k}']:.4f} | {best['mean_latency_ms']:.1f} | "
            f"{best['mean_generation_ms']:.1f} | {best['mean_execution_ms']:.1f} |"
        )
    lines.extend(["", "## Detailed Results", ""])
    for result in output["results"]:
        summary_rows = result.get("summary", [])
        if summary_rows and "mean_generation_ms" not in summary_rows[0]:
            summary_rows = summarize_public_systems(result["systems"], k=k)
        result_for_interpretation = {**result, "summary": summary_rows}
        lines.extend(
            [
                f"### {result['display_name']}",
                "",
                f"Source: {result['source_url']}",
                "",
                f"Setting: {result['setting']}",
                "",
            ]
        )
        for note in result["notes"]:
            lines.append(f"- {note}")
        lines.extend(
            [
                "",
                f"| System | Recall@{k} | nDCG@{k} | MRR@{k} | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in summary_rows:
            lines.append(
                f"| `{row['system']}` | {row[f'recall@{k}']:.4f} | {row[f'ndcg@{k}']:.4f} | "
                f"{row[f'mrr@{k}']:.4f} | {row['mean_latency_ms']:.1f} | "
                f"{row['mean_generation_ms']:.1f} | {row['mean_execution_ms']:.1f} | "
                f"{row['mean_search_calls']:.2f} | {row['mean_rerank_pairs']:.1f} |"
            )
        lines.extend(["", *render_public_interpretation(result_for_interpretation, k), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_public_interpretation(result: dict, k: int) -> list[str]:
    summary = {row["system"]: row for row in result["summary"]}
    generated = summary.get("generated_search_as_code")
    reflective = summary.get("generated_reflective_search_as_code")
    fixed = (
        summary.get("fixed_understanding_rewrite_hybrid_rerank")
        or summary.get("fixed_hybrid_rerank")
        or summary.get("fixed_hybrid")
    )
    lines = ["Interpretation:"]
    if generated and fixed:
        delta = generated[f"recall@{k}"] - fixed[f"recall@{k}"]
        lines.append(
            f"- Generated Search-as-Code delta vs strongest fixed baseline on Recall@{k}: `{delta:+.4f}`."
        )
    if reflective and generated:
        delta = reflective[f"recall@{k}"] - generated[f"recall@{k}"]
        lines.append(f"- Reflective generated delta vs one-shot generated Recall@{k}: `{delta:+.4f}`.")
    if result["benchmark_id"].startswith("beir/"):
        lines.append("- BEIR is mostly a retrieval-quality sanity check; it does not isolate enterprise-style tool control.")
    if result["benchmark_id"] == "hotpotqa/distractor":
        lines.append("- HotpotQA adds multi-hop pressure, but this slice uses pooled distractor contexts rather than fullwiki retrieval.")
    return lines


if __name__ == "__main__":
    main()
