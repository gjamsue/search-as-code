# Real LLM Codegen Smoke

This is a small proof that the repository can run true model-generated
Search-as-Code, not only the deterministic proxy used for the full checked-in
benchmark tables.

- Provider: `codex-cli`
- Auth path: local Codex app login, no `OPENAI_API_KEY` required
- Benchmark slice: BEIR/SciFact, 5,183 documents, 1 query
- Query: `0-dimensional biomaterials show inductive properties.`
- System: `real_codegen_search_as_code`

## Result

| System | Recall@10 | Total ms | Codegen ms | Execution ms | Search calls | Rerank pairs | Candidate pool |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fixed_understanding_rewrite_hybrid_rerank` | 0.0000 | 224.4 | 0.0 | 224.4 | 1.0 | 20.0 | 20.0 |
| `real_codegen_search_as_code` | 0.0000 | 49495.5 | 49230.0 | 265.5 | 3.0 | 1.0 | 1.0 |

This is intentionally a smoke test, not a benchmark claim. It verifies that
Codex generated Python from the Search-as-Code skill/tool contract, the AST
guard accepted it, and the generated program executed against the real local
SciFact index.

Latency is reported as total wall time, code generation time, and execution
time. For real codegen, code generation dominates this smoke run; cached reuse
uses the same generated program and mostly pays execution time.

## Generated Flow

The generated program:

- ran query understanding and extracted entity text from `analysis["entities"]`
- called entity linking only when entity text existed
- called query rewrite and read `rewrite_result.get("rewrites", [])`
- chose `hybrid` search with `bm25_weight=0.7`
- searched the original query plus rewrites/subqueries
- deduped by `doc_id`
- reranked a bounded candidate pool
- logged `agentic_plan` and `reflection`

Trace excerpt:

```json
[
  {
    "event": "agentic_plan",
    "payload": {
      "mode": "hybrid",
      "bm25_weight": 0.7,
      "rewrite_count": 2,
      "candidate_limit": 20
    }
  },
  {
    "event": "reflection",
    "payload": {
      "searched_queries": 3,
      "deduped_candidates": 1,
      "returned_hits": 1
    }
  }
]
```

## Readout

The important finding is operational: real codegen now works through a reusable
skill and can run without an API key by using the local Codex CLI. The current
full benchmark tables should still be read as deterministic Search-as-Code proxy
results. Next we should scale `real_codegen_search_as_code` to a 30-100 query
sample and track codegen latency, invalid-code rate, repair rate, retrieval
quality, and token cost.
