---
name: search-as-code-codegen
description: Generate safe Search-as-Code retrieval programs for benchmarks or demos. Use when asked to write real model-generated retrieval code, Search-as-Code flows, dynamic search-stack control, query rewrite/search/rerank orchestration, or agentic retrieval code.
---

# Search-as-Code Codegen

Generate a Python retrieval program that runs inside the benchmark `FlowContext`.
The output must be executable code, not prose, unless the user asks for an
explanation.

## Runtime Contract

Write:

```python
def run(ctx):
    ...
    return {"hits": ranked_hits, "candidates": candidates}
```

Available context:

- `ctx.query`: original user query.
- `ctx.query_understanding.analyze(query)` returns a dict:
  `entities` is a list of dicts with `text` and `label`; `noun_chunks`,
  `intents`, and `subqueries` are lists of strings. Extract entity text with
  `entity.get("text", "")` before joining.
- `ctx.entity_linking.link(text)`: links extracted entities when useful.
- `ctx.query_rewrite.should_rewrite(query, analysis)` returns a boolean.
- `ctx.query_rewrite.rewrite(query, analysis=analysis, linked_entities=linked_entities)` returns a dict:
  `{"needed": bool, "rewrites": [str, ...], "method": str}`. Pass `analysis` and
  `linked_entities` as keyword arguments.
- `ctx.search.search(query, mode="bm25"|"dense"|"hybrid", top_k=N, bm25_weight=0.55, include_doc_types=[...], exclude_doc_types=[...], include_sources=[...], exclude_sources=[...], must_terms=[...], should_terms=[...], exclude_terms=[...])`.
- `ctx.search.bm25(query, top_k=N, filters={"doc_type": [...], "source": [...]}, ...)`, `ctx.search.dense(...)`, and `ctx.search.hybrid(...)` are convenience wrappers over `ctx.search.search(...)`.
- Search hits are immutable `SearchCandidate` objects with `doc_id`, `title`, `text`, `metadata`, `score`, plus read-only convenience properties such as `doc_type`, `source`, `customer`, `product`, `owner`, `ticket`, `cve`, `version`, `fixed_version`, `severity`, and `date`.
- `ctx.ranking.rerank(query, candidates, top_k=N)` or `ctx.rerank(query, candidates, top_k=N)`.
- `ctx.log(event, payload)` for plan/reflection traces.
- Set `ctx.candidate_pool = len(candidates)` before returning.

## Required Behavior

- Use dynamic routes. Do not always run the same flow.
- Preserve exact IDs and versions with BM25 routes.
- Use dense or hybrid routes for long, vague, multi-hop, or semantic queries.
- Use query understanding, rewrite, and entity linking when the query is long, comparative, entity-heavy, or under-specified.
- Treat rewrite output as a dict and read `rewrite_result.get("rewrites", [])`.
- Deduplicate candidates by `doc_id`; keep the higher score.
- Rerank only a bounded candidate pool.
- Return top evidence as `hits`; include the merged pool as `candidates` when available.
- Log an `agentic_plan` and a `reflection` event.

## Safety

Do not import modules, read files, write files, make network calls, spawn
processes, use `eval`/`exec`, or access private/dunder attributes. The code
must only use `ctx` tools, local helper functions, and normal Python containers.

## Output Style

When a schema asks for JSON, return:

```json
{"code": "def run(ctx):\n    ...", "rationale": "short reason"}
```

When the user asks for code only, return only the Python code.
