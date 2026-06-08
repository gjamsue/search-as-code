"""FastAPI server exposing the real open-source search stack.

Run:
    .venv/bin/python -m real_search_stack.api_server

Then call:
    POST /query_understanding
    POST /entity_linking
    POST /search
    POST /rerank
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from .apis import (
    IndexedDocument,
    RealEntityLinkingAPI,
    RealHybridSearchAPI,
    RealQueryUnderstandingAPI,
    RealRankingAPI,
    SearchCandidate,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "sac_benchmark_dataset" / "data" / "corpus.jsonl"


def _dataset_documents() -> list[IndexedDocument]:
    documents = []
    with CORPUS_PATH.open() as handle:
        for line in handle:
            doc = json.loads(line)
            documents.append(
                IndexedDocument(
                    doc_id=doc["doc_id"],
                    title=doc["title"],
                    text=doc["text"],
                    metadata=doc.get("metadata", {}),
                )
            )
    return documents


app = FastAPI(title="Real Search-as-Code APIs")

query_understanding_api = RealQueryUnderstandingAPI()
entity_linking_api = RealEntityLinkingAPI()
search_api = RealHybridSearchAPI(_dataset_documents())
ranking_api = RealRankingAPI()


class TextRequest(BaseModel):
    text: str


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    top_k: int = 10


class RerankRequest(BaseModel):
    query: str
    candidates: list[dict]
    top_k: int = 5


@app.post("/query_understanding")
def query_understanding(req: TextRequest) -> dict:
    return query_understanding_api.analyze(req.text)


@app.post("/entity_linking")
def entity_linking(req: TextRequest) -> dict:
    return {"entities": entity_linking_api.link(req.text)}


@app.post("/search")
def search(req: SearchRequest) -> dict:
    hits = search_api.search(req.query, top_k=req.top_k, mode=req.mode)
    return {"hits": [hit.compact() for hit in hits]}


@app.post("/rerank")
def rerank(req: RerankRequest) -> dict:
    candidates = [
        SearchCandidate(
            doc_id=item["id"],
            title=item.get("title", ""),
            text=item.get("text", item.get("snippet", "")),
            metadata=item.get("metadata", {}),
            score=float(item.get("score", 0.0)),
            bm25_score=float(item.get("bm25_score", 0.0)),
            dense_score=float(item.get("dense_score", 0.0)),
        )
        for item in req.candidates
    ]
    ranked = ranking_api.rerank(req.query, candidates, top_k=req.top_k)
    return {"hits": [hit.compact() for hit in ranked]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
