"""Real LLM-backed Search-as-Code generation and safe execution helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import time
from typing import Any

import requests

from real_search_stack.apis import SearchCandidate


ROOT = Path(__file__).resolve().parent
DEFAULT_CODEX_CLI = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
VALID_DOC_TYPES = [
    "account_brief",
    "alias_registry",
    "approval_ledger",
    "authority_matrix",
    "escalation",
    "guide",
    "meeting_note",
    "policy",
    "product_footprint",
    "release",
    "roadmap",
    "runbook",
    "sales_discovery",
    "security_advisory",
    "security_ticket",
    "war_room_roster",
]
VALID_SOURCES = [
    "crm",
    "eval_policy",
    "governance",
    "jira",
    "release_notes",
    "roadmap",
    "runbook",
    "security",
    "source_of_truth",
    "support",
    "vendor_advisory",
]
COMMON_DISTRACTOR_HINTS = [
    "dashboard_snapshot_distractor",
    "draft_policy_distractor",
    "meeting_note_distractor",
    "memo_distractor",
    "review_note_distractor",
    "slack_thread_distractor",
]

CODEGEN_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "Python source containing def run(ctx)."},
        "rationale": {"type": "string", "description": "Short explanation of route choices."},
    },
    "required": ["code", "rationale"],
    "additionalProperties": False,
}


@dataclass
class LLMCodegenResult:
    code: str
    rationale: str
    provider: str
    model: str
    latency_ms: float
    cache_hit: bool
    static_repairs: int = 0


class LLMSearchCodeGenerator:
    """Generate Search-as-Code programs with a real model provider."""

    def __init__(
        self,
        *,
        provider: str = "codex-cli",
        model: str = "",
        timeout_seconds: int = 120,
        cache_dir: str | Path = ".llm_codegen_cache",
        codex_cli: str = DEFAULT_CODEX_CLI,
        codex_reasoning_effort: str = "low",
    ) -> None:
        self.provider = provider
        self.model = model or default_model(provider)
        self.timeout_seconds = timeout_seconds
        self.cache_dir = Path(cache_dir)
        self.codex_cli = codex_cli
        self.codex_reasoning_effort = codex_reasoning_effort
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        query: str,
        *,
        top_k: int,
        candidate_k: int,
        benchmark_hint: str = "",
    ) -> LLMCodegenResult:
        cache_key = self._cache_key(query, top_k=top_k, candidate_k=candidate_k, benchmark_hint=benchmark_hint)
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return LLMCodegenResult(
                code=payload["code"],
                rationale=payload.get("rationale", ""),
                provider=payload.get("provider", self.provider),
                model=payload.get("model", self.model),
                latency_ms=payload.get("latency_ms", 0.0),
                cache_hit=True,
                static_repairs=payload.get("static_repairs", 0),
            )

        prompt = build_codegen_prompt(
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            benchmark_hint=benchmark_hint,
            compact=self.provider == "codex-cli",
        )
        started = time.perf_counter()
        payload = self._generate_from_prompt(prompt)
        static_repairs = 0
        try:
            code = validate_generated_code(payload["code"])
        except Exception as exc:
            static_repairs += 1
            repair_prompt = build_repair_prompt(
                query,
                payload["code"],
                exc,
                top_k=top_k,
                candidate_k=candidate_k,
                benchmark_hint=f"{benchmark_hint}; static validation failed before execution",
                compact=self.provider == "codex-cli",
            )
            payload = self._generate_from_prompt(repair_prompt)
            code = validate_generated_code(payload["code"])
        latency_ms = (time.perf_counter() - started) * 1000

        result = {
            "code": code,
            "rationale": payload.get("rationale", ""),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": round(latency_ms, 3),
            "static_repairs": static_repairs,
        }
        cache_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return LLMCodegenResult(cache_hit=False, **result)

    def repair(
        self,
        query: str,
        code: str,
        error: Exception,
        *,
        top_k: int,
        candidate_k: int,
        benchmark_hint: str = "",
    ) -> LLMCodegenResult:
        cache_key = self._cache_key(
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            benchmark_hint=f"{benchmark_hint}\nrepair:{type(error).__name__}:{str(error)}:{hashlib.sha256(code.encode('utf-8')).hexdigest()[:12]}",
        )
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return LLMCodegenResult(
                code=payload["code"],
                rationale=payload.get("rationale", ""),
                provider=payload.get("provider", self.provider),
                model=payload.get("model", self.model),
                latency_ms=payload.get("latency_ms", 0.0),
                cache_hit=True,
                static_repairs=payload.get("static_repairs", 0),
            )

        prompt = build_repair_prompt(
            query,
            code,
            error,
            top_k=top_k,
            candidate_k=candidate_k,
            benchmark_hint=benchmark_hint,
            compact=self.provider == "codex-cli",
        )
        started = time.perf_counter()
        payload = self._generate_from_prompt(prompt)
        static_repairs = 0
        try:
            repaired_code = validate_generated_code(payload["code"])
        except Exception as exc:
            static_repairs += 1
            repair_prompt = build_repair_prompt(
                query,
                payload["code"],
                exc,
                top_k=top_k,
                candidate_k=candidate_k,
                benchmark_hint=f"{benchmark_hint}; static validation failed during repair",
                compact=self.provider == "codex-cli",
            )
            payload = self._generate_from_prompt(repair_prompt)
            repaired_code = validate_generated_code(payload["code"])
        latency_ms = (time.perf_counter() - started) * 1000

        result = {
            "code": repaired_code,
            "rationale": payload.get("rationale", ""),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": round(latency_ms, 3),
            "static_repairs": static_repairs,
        }
        cache_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return LLMCodegenResult(cache_hit=False, **result)

    def reflect(
        self,
        query: str,
        code: str,
        observation: dict[str, Any],
        *,
        top_k: int,
        candidate_k: int,
        benchmark_hint: str = "",
    ) -> LLMCodegenResult:
        observation_text = json.dumps(observation, sort_keys=True, default=str)
        cache_key = self._cache_key(
            query,
            top_k=top_k,
            candidate_k=candidate_k,
            benchmark_hint=f"{benchmark_hint}\nreflection:{hashlib.sha256((code + observation_text).encode('utf-8')).hexdigest()[:16]}",
        )
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return LLMCodegenResult(
                code=payload["code"],
                rationale=payload.get("rationale", ""),
                provider=payload.get("provider", self.provider),
                model=payload.get("model", self.model),
                latency_ms=payload.get("latency_ms", 0.0),
                cache_hit=True,
                static_repairs=payload.get("static_repairs", 0),
            )

        prompt = build_reflection_prompt(
            query,
            code,
            observation,
            top_k=top_k,
            candidate_k=candidate_k,
            benchmark_hint=benchmark_hint,
            compact=self.provider == "codex-cli",
        )
        started = time.perf_counter()
        payload = self._generate_from_prompt(prompt)
        static_repairs = 0
        try:
            reflected_code = validate_generated_code(payload["code"])
        except Exception as exc:
            static_repairs += 1
            repair_prompt = build_repair_prompt(
                query,
                payload["code"],
                exc,
                top_k=top_k,
                candidate_k=candidate_k,
                benchmark_hint=f"{benchmark_hint}; static validation failed during reflection",
                compact=self.provider == "codex-cli",
            )
            payload = self._generate_from_prompt(repair_prompt)
            reflected_code = validate_generated_code(payload["code"])
        latency_ms = (time.perf_counter() - started) * 1000

        result = {
            "code": reflected_code,
            "rationale": payload.get("rationale", ""),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": round(latency_ms, 3),
            "static_repairs": static_repairs,
        }
        cache_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return LLMCodegenResult(cache_hit=False, **result)

    def _generate_from_prompt(self, prompt: str) -> dict[str, str]:
        if self.provider == "openai":
            return self._generate_openai(prompt)
        if self.provider == "codex-cli":
            return self._generate_codex_cli(prompt)
        raise ValueError(f"Unsupported LLM codegen provider: {self.provider}")

    def _cache_key(self, query: str, *, top_k: int, candidate_k: int, benchmark_hint: str) -> str:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "query": query,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "benchmark_hint": benchmark_hint,
            "prompt_version": 5,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]

    def _generate_openai(self, prompt: str) -> dict[str, str]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --real-codegen-provider openai")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        response = requests.post(
            f"{base_url}/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "input": prompt,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "search_as_code_program",
                        "schema": CODEGEN_RESPONSE_SCHEMA,
                        "strict": True,
                    }
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        text = extract_response_text(response.json())
        return parse_codegen_json(text)

    def _generate_codex_cli(self, prompt: str) -> dict[str, str]:
        if not Path(self.codex_cli).exists():
            raise RuntimeError(f"Codex CLI not found: {self.codex_cli}")
        with tempfile.TemporaryDirectory(prefix="sac-codegen-") as tmp:
            tmp_path = Path(tmp)
            schema_path = tmp_path / "schema.json"
            output_path = tmp_path / "output.json"
            schema_path.write_text(json.dumps(CODEGEN_RESPONSE_SCHEMA), encoding="utf-8")
            cmd = [
                self.codex_cli,
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--cd",
                str(ROOT),
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
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=self.timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"Codex CLI codegen failed with exit {completed.returncode}:\n{completed.stdout[-4000:]}")
            if not output_path.exists():
                raise RuntimeError(f"Codex CLI did not write structured output:\n{completed.stdout[-4000:]}")
            return parse_codegen_json(output_path.read_text(encoding="utf-8"))


def default_model(provider: str) -> str:
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    if provider == "codex-cli":
        return os.environ.get("CODEX_MODEL", "")
    return ""


def build_codegen_prompt(
    query: str,
    *,
    top_k: int,
    candidate_k: int,
    benchmark_hint: str,
    compact: bool = False,
) -> str:
    if compact:
        return textwrap.dedent(
            f"""
            Use the search-as-code-codegen skill. Return JSON only with fields code and rationale.

            Write Python source for def run(ctx): using ctx tools.
            Query: {query}
            Benchmark: {benchmark_hint or "general retrieval benchmark"}
            Constants: TOP_K={top_k}, CANDIDATE_K={candidate_k}
            Real doc_types: {", ".join(VALID_DOC_TYPES)}
            Real sources: {", ".join(VALID_SOURCES)}
            Common distractors: {", ".join(COMMON_DISTRACTOR_HINTS)}

            Must:
            - dynamically choose BM25/dense/hybrid/search rewrites based on the query
            - use actual doc_type/source values listed above; do not invent values like ticket, issue, release_note, changelog, advisory, or customer_status
            - call ctx.query_rewrite.rewrite(query, analysis=analysis, linked_entities=linked_entities)
            - treat rewrite_result as dict and use rewrite_result.get("rewrites", [])
            - analysis["entities"] contains dicts; join entity.get("text", ""), not raw dicts
            - search hits are immutable SearchCandidate objects; never assign into hit[...] or hit.attr
            - if you need route annotations or adjusted scores, keep side dictionaries keyed by doc_id or copy hit.as_dict()
            - dedupe by doc_id, rerank at most CANDIDATE_K, set ctx.candidate_pool
            - preserve high-confidence evidence before rerank; do not let follow-up noise bury exact IDs or source-of-truth docs
            - log agentic_plan and reflection
            - return {{"hits": ranked_hits, "candidates": candidates}}
            - no imports, files, network, subprocess, eval, exec, globals, locals, or dunder/private access
            """
        ).strip()
    return textwrap.dedent(
        f"""
        Use the search-as-code-codegen skill. Generate a real Search-as-Code retrieval program.

        Return JSON matching this schema only:
        {json.dumps(CODEGEN_RESPONSE_SCHEMA, indent=2)}

        Query:
        {query}

        Benchmark hint:
        {benchmark_hint or "general retrieval benchmark"}

        Runtime constants:
        - TOP_K = {top_k}
        - CANDIDATE_K = {candidate_k}

        Available APIs:
        - ctx.query
        - ctx.query_understanding.analyze(query)
          Returns a dict. analysis["entities"] is a list of dicts with text/label/start/end.
          analysis["noun_chunks"], analysis["intents"], and analysis["subqueries"] are string lists.
        - ctx.entity_linking.link(text)
        - ctx.query_rewrite.should_rewrite(query, analysis)
        - ctx.query_rewrite.rewrite(query, analysis=analysis, linked_entities=linked_entities)
          Returns {"needed": bool, "rewrites": [str, ...], "method": str}.
          analysis and linked_entities must be passed as keyword arguments.
        - ctx.search.search(query, mode="bm25"|"dense"|"hybrid", top_k=N, bm25_weight=0.0..1.0,
          include_doc_types=[...], exclude_doc_types=[...], include_sources=[...],
          exclude_sources=[...], must_terms=[...], should_terms=[...], exclude_terms=[...])
        - ctx.ranking.rerank(query, candidates, top_k=N)
        - ctx.log(event, payload)

        Real metadata values:
        - Authoritative doc_types: {", ".join(VALID_DOC_TYPES)}
        - Authoritative sources: {", ".join(VALID_SOURCES)}
        - Common distractor doc_types to avoid/downweight: {", ".join(COMMON_DISTRACTOR_HINTS)}

        Program requirements:
        - Define exactly one entrypoint: def run(ctx):
        - Use dynamic control flow and route choices based on the query.
        - Use BM25 for exact names, IDs, dates, versions, and short entity-heavy queries.
        - Use hybrid or dense for long, semantic, multi-hop, or paraphrased queries.
        - Use actual doc_type/source values listed above; do not invent metadata filters such as ticket, issue, release_note, changelog, advisory, or customer_status.
        - Use query understanding and rewrite when it is likely useful.
        - Treat query rewrite output as a dict; read rewrite_result.get("rewrites", []).
        - Extract entity text with entity.get("text", "") before joining entities.
        - Search hits are immutable SearchCandidate objects with doc_id/title/text/metadata/score.
        - Never assign into hit[...] or hit.attr. If you need route annotations or adjusted scores, keep side dictionaries keyed by doc_id or copy hit.as_dict().
        - Merge candidates by doc_id and dedupe before reranking.
        - Keep reranking bounded to at most CANDIDATE_K candidates.
        - Preserve high-confidence evidence across branches before rerank; do not let follow-up noise bury exact IDs or source-of-truth docs.
        - Set ctx.candidate_pool.
        - Log agentic_plan and reflection events.
        - Return {{"hits": ranked_hits, "candidates": merged_candidates}}.

        Safety requirements:
        - No imports.
        - No file, network, subprocess, eval, exec, globals, locals, or dunder/private attribute access.
        - Use only ctx tools, helper functions you define, and normal Python containers.
        """
    ).strip()


def build_repair_prompt(
    query: str,
    code: str,
    error: Exception,
    *,
    top_k: int,
    candidate_k: int,
    benchmark_hint: str,
    compact: bool = False,
) -> str:
    error_text = f"{type(error).__name__}: {error}"
    base = textwrap.dedent(
        f"""
        Use the search-as-code-codegen skill. Repair this Search-as-Code program.

        Query:
        {query}

        Benchmark hint:
        {benchmark_hint or "general retrieval benchmark"}

        Runtime constants:
        - TOP_K = {top_k}
        - CANDIDATE_K = {candidate_k}

        Execution error:
        {error_text}

        Current code:
        ```python
        {code}
        ```

        Return JSON only with fields code and rationale. Keep the same def run(ctx)
        contract. Fix the actual runtime error and preserve dynamic search-stack
        control, dedupe, bounded rerank, agentic_plan logging, and reflection logging.

        Important SDK facts:
        - analysis["entities"] is a list of dicts; use entity.get("text", "") before joining.
        - query rewrite returns a dict; use rewrite_result.get("rewrites", []).
        - search hits are immutable SearchCandidate objects; never assign into hit[...] or hit.attr.
        - if annotations are needed, keep side dictionaries keyed by doc_id or copy hit.as_dict().
        - use real doc_types only: {", ".join(VALID_DOC_TYPES)}.
        - No imports, files, network, subprocess, eval, exec, globals, locals, or dunder/private access.
        """
    ).strip()
    if compact:
        return base
    return base + "\n\nReturn JSON matching this schema only:\n" + json.dumps(CODEGEN_RESPONSE_SCHEMA, indent=2)


def build_reflection_prompt(
    query: str,
    code: str,
    observation: dict[str, Any],
    *,
    top_k: int,
    candidate_k: int,
    benchmark_hint: str,
    compact: bool = False,
) -> str:
    observation_json = json.dumps(observation, indent=2, default=str)[:12000]
    base = textwrap.dedent(
        f"""
        Use the search-as-code-codegen skill. You are doing agentic Search-as-Code.

        Query:
        {query}

        Benchmark hint:
        {benchmark_hint or "enterprise retrieval benchmark"}

        Runtime constants:
        - TOP_K = {top_k}
        - CANDIDATE_K = {candidate_k}

        Initial generated program:
        ```python
        {code}
        ```

        Observation after running the initial program:
        ```json
        {observation_json}
        ```

        Return JSON only with fields code and rationale.

        Task:
        - Reflect on whether the observed evidence looks complete for the query.
        - Generate a complete replacement `def run(ctx):` program.
        - First preserve any observed high-confidence authoritative docs, exact identifiers, final approval/policy/release docs, and customer/account evidence.
        - If the initial evidence looks incomplete, add targeted follow-up retrieval:
          exact identifier routes, source-authority filters, alias expansion,
          policy/ledger searches, release/advisory/ticket fanout, or negative-evidence routes as needed.
        - If top hits are mostly distractors or decoys, add filters/downweighting for those doc_types but keep broader fallback routes.
        - If the initial evidence looks sufficient, you may return a cleaned-up equivalent program.
        - Do not use ground truth labels; infer from query, trace, top hits, doc metadata, and missing evidence categories.
        - Log both `agentic_plan` and `reflection`.

        Important SDK facts:
        - analysis["entities"] is a list of dicts; use entity.get("text", "") before joining.
        - query rewrite returns a dict; use rewrite_result.get("rewrites", []).
        - search hits are immutable SearchCandidate objects with doc_id/title/text/metadata/score.
        - Never assign into hit[...] or hit.attr. If you need route annotations or adjusted scores, keep side dictionaries keyed by doc_id or copy hit.as_dict().
        - Use actual doc_type/source values only:
          doc_types={VALID_DOC_TYPES}
          sources={VALID_SOURCES}
        - No imports, files, network, subprocess, eval, exec, globals, locals, or dunder/private access.
        """
    ).strip()
    if compact:
        return base
    return base + "\n\nReturn JSON matching this schema only:\n" + json.dumps(CODEGEN_RESPONSE_SCHEMA, indent=2)


def parse_codegen_json(text: str) -> dict[str, str]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    if not isinstance(payload, dict) or not isinstance(payload.get("code"), str):
        raise ValueError("Codegen response must be a JSON object with string field 'code'")
    return {"code": payload["code"], "rationale": str(payload.get("rationale", ""))}


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict):
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
    if parts:
        return "\n".join(parts)
    raise ValueError("Could not extract text from Responses API payload")


DISALLOWED_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Raise,
    ast.Delete,
)
DISALLOWED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "dir",
    "eval",
    "exec",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
SAFE_BUILTINS = {
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "abs": abs,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def safe_getattr(obj, name: str, default=None):
    if str(name).startswith("_"):
        raise AttributeError("private attribute access is not allowed")
    return getattr(obj, name, default)


SAFE_BUILTINS["getattr"] = safe_getattr


def safe_hasattr(obj, name: str):
    if str(name).startswith("_"):
        return False
    return hasattr(obj, name)


SAFE_BUILTINS["hasattr"] = safe_hasattr


def validate_generated_code(code: str) -> str:
    code = strip_code_fence(code)
    tree = ast.parse(code)
    run_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"]
    if len(run_defs) != 1:
        raise ValueError("Generated code must define exactly one def run(ctx)")
    run_def = run_defs[0]
    if len(run_def.args.args) != 1 or run_def.args.args[0].arg != "ctx":
        raise ValueError("Generated run function must accept exactly one argument named ctx")

    for node in ast.walk(tree):
        if isinstance(node, DISALLOWED_AST_NODES):
            raise ValueError(f"Generated code uses disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Generated code cannot access dunder attributes")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Generated code cannot access dunder names")
        if isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            if call_name in DISALLOWED_CALLS:
                raise ValueError(f"Generated code calls disallowed function: {call_name}")
    return code


def strip_code_fence(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        code = re.sub(r"^```(?:python)?\s*", "", code)
        code = re.sub(r"\s*```$", "", code)
    return code.strip()


def execute_llm_generated_program(code: str, ctx, *, top_k: int, candidate_k: int) -> dict:
    code = validate_generated_code(code)
    namespace: dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "TOP_K": top_k,
        "CANDIDATE_K": candidate_k,
    }
    exec(compile(code, "<llm_search_as_code>", "exec"), namespace)
    result = namespace["run"](ctx)
    if not isinstance(result, dict) or "hits" not in result:
        raise ValueError("Generated run(ctx) must return a dict with a 'hits' key")
    result["hits"] = [coerce_generated_candidate(hit) for hit in result.get("hits", [])]
    if "candidates" in result:
        result["candidates"] = [coerce_generated_candidate(hit) for hit in result.get("candidates", [])]
    return result


def coerce_generated_candidate(candidate: SearchCandidate | dict) -> SearchCandidate:
    if isinstance(candidate, SearchCandidate):
        return candidate
    if not isinstance(candidate, dict):
        raise ValueError(f"Generated candidate must be SearchCandidate or dict, got {type(candidate).__name__}")
    metadata = candidate.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    extras = {
        key: value
        for key, value in candidate.items()
        if key not in {"doc_id", "id", "title", "text", "metadata", "score", "bm25_score", "dense_score"}
    }
    return SearchCandidate(
        doc_id=str(candidate.get("doc_id") or candidate.get("id") or ""),
        title=str(candidate.get("title") or ""),
        text=str(candidate.get("text") or ""),
        metadata={**metadata, **extras},
        score=float(candidate.get("score") or 0.0),
        bm25_score=float(candidate.get("bm25_score") or 0.0),
        dense_score=float(candidate.get("dense_score") or 0.0),
    )
