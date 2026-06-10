"""Real open-source APIs for search, reranking, query understanding, and entity linking.

These classes are deliberately small wrappers around real open-source
components:
- rank_bm25 for lexical retrieval
- sentence-transformers for dense embedding retrieval
- sentence-transformers CrossEncoder for reranking
- spaCy en_core_web_sm for query analysis and entity mention extraction
- Wikidata wbsearchentities for public entity linking

The wrappers are usable directly in scripts and can also be exposed through
FastAPI by `api_server.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Iterable
from urllib import parse, request

import numpy as np
from rank_bm25 import BM25Okapi
import spacy
from sentence_transformers import CrossEncoder, SentenceTransformer


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-+.]*")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class IndexedDocument:
    doc_id: str
    title: str
    text: str
    metadata: dict


@dataclass(frozen=True)
class SearchCandidate:
    doc_id: str
    title: str
    text: str
    metadata: dict
    score: float
    bm25_score: float
    dense_score: float

    @property
    def id(self) -> str:
        return self.doc_id

    @property
    def doc_type(self) -> str:
        return str(self.metadata.get("doc_type", ""))

    @property
    def source(self) -> str:
        return str(self.metadata.get("source", ""))

    @property
    def customer(self) -> str:
        return str(self.metadata.get("customer", ""))

    @property
    def product(self) -> str:
        return str(self.metadata.get("product", ""))

    @property
    def owner(self) -> str:
        return str(self.metadata.get("owner", ""))

    @property
    def ticket(self) -> str:
        return str(self.metadata.get("ticket", ""))

    @property
    def cve(self) -> str:
        return str(self.metadata.get("cve", ""))

    @property
    def version(self) -> str:
        return str(self.metadata.get("version") or self.metadata.get("fixed_version", ""))

    @property
    def fixed_version(self) -> str:
        return str(self.metadata.get("fixed_version") or self.metadata.get("version", ""))

    @property
    def severity(self) -> str:
        return str(self.metadata.get("severity", ""))

    @property
    def date(self) -> str:
        return str(self.metadata.get("date", ""))

    def as_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "metadata": self.metadata,
            "score": self.score,
            "bm25_score": self.bm25_score,
            "dense_score": self.dense_score,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __contains__(self, key: str) -> bool:
        return key in self.as_dict()

    def items(self):
        return self.as_dict().items()

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def compact(self, max_chars: int = 240) -> dict:
        snippet = self.text[:max_chars].replace("\n", " ").strip()
        if len(self.text) > max_chars:
            snippet += "..."
        return {
            "id": self.doc_id,
            "title": self.title,
            "score": round(float(self.score), 4),
            "bm25_score": round(float(self.bm25_score), 4),
            "dense_score": round(float(self.dense_score), 4),
            "metadata": self.metadata,
            "snippet": snippet,
        }


class RealQueryUnderstandingAPI:
    """Query understanding using spaCy plus deterministic planning hints."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self.nlp = spacy.load(model_name)

    def analyze(self, query: str) -> dict:
        doc = self.nlp(query)
        entities = [
            {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
            for ent in doc.ents
        ]
        noun_chunks = [chunk.text for chunk in doc.noun_chunks]
        lower = query.lower()
        query_tokens = set(tokenize(query))
        intents = []
        if any(term in query_tokens for term in ["compare", "contrast", "different", "versus", "vs"]):
            intents.append("compare")
        if any(term in query_tokens for term in ["metric", "metrics", "latency", "token", "tokens", "relevance", "score", "percent"]):
            intents.append("metrics")
        if any(term in query_tokens for term in ["how", "mechanically", "mechanism", "pipeline", "flow", "works"]):
            intents.append("mechanics")
        if any(term in query_tokens for term in ["next", "decision", "recommend", "should", "strategy"]):
            intents.append("decision_support")
        if not intents:
            intents.append("answer")

        subqueries = [query]
        for chunk in noun_chunks[:4]:
            if len(chunk.split()) >= 2 and chunk.lower() not in lower:
                subqueries.append(chunk)
        if "compare" in intents:
            subqueries.extend(self._comparison_subqueries(query))

        return {
            "query": query,
            "entities": entities,
            "noun_chunks": noun_chunks,
            "intents": intents,
            "subqueries": _unique(subqueries),
        }

    def _comparison_subqueries(self, query: str) -> list[str]:
        parts = re.split(r"\b(?:and|versus|vs|compare)\b", query, flags=re.I)
        return [part.strip(" .?") for part in parts if len(part.strip()) > 8]


class RealEntityLinkingAPI:
    """Entity linking using spaCy mention extraction plus Wikidata search.

    For enterprise production, replace Wikidata with the company's canonical
    entity graph or an open-source linker such as BLINK, REL, or OpenTapioca.
    """

    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        *,
        wikidata_enabled: bool = True,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.nlp = spacy.load(model_name)
        self.wikidata_enabled = wikidata_enabled
        self.timeout_seconds = timeout_seconds

    def link(self, text: str) -> list[dict]:
        doc = self.nlp(text)
        seen = set()
        results = []
        for ent in doc.ents:
            key = (ent.text.lower(), ent.label_)
            if key in seen:
                continue
            seen.add(key)
            wikidata_match = self._wikidata_lookup(ent.text) if self.wikidata_enabled else None
            if wikidata_match:
                results.append(
                    {
                        "mention": ent.text,
                        "ner_label": ent.label_,
                        "entity": wikidata_match["label"],
                        "qid": wikidata_match["qid"],
                        "url": f"https://www.wikidata.org/wiki/{wikidata_match['qid']}",
                        "linked_text": wikidata_match.get("linked_text", ent.text),
                        "description": wikidata_match.get("description", ""),
                        "confidence": 0.85,
                        "method": "spacy_ner+wikidata_search",
                    }
                )
            else:
                results.append(
                    {
                        "mention": ent.text,
                        "ner_label": ent.label_,
                        "entity": ent.text,
                        "confidence": 0.5,
                        "method": "spacy_ner_fallback",
                    }
                )
        return results

    def _wikidata_lookup(self, mention: str) -> dict | None:
        for candidate in self._wikidata_candidates(mention):
            match = self._wikidata_lookup_one(candidate)
            if match:
                match["linked_text"] = candidate
                return match
        return None

    def _wikidata_candidates(self, mention: str) -> list[str]:
        candidates = [mention]
        words = mention.split()
        suffixes = {"ai", "search", "agent", "agentic", "model", "waldo"}
        while len(words) > 1 and words[-1].lower() in suffixes:
            words = words[:-1]
            candidates.append(" ".join(words))
        if len(words) > 1:
            candidates.append(words[0])
        return _unique(candidates)

    def _wikidata_lookup_one(self, mention: str) -> dict | None:
        params = parse.urlencode(
            {
                "action": "wbsearchentities",
                "format": "json",
                "language": "en",
                "limit": 1,
                "search": mention,
            }
        )
        url = f"https://www.wikidata.org/w/api.php?{params}"
        req = request.Request(
            url,
            headers={
                "User-Agent": "real-search-as-code-demo/0.1 "
                "(https://www.wikidata.org/wiki/Wikidata:Data_access)"
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        hits = payload.get("search", [])
        if not hits:
            return None
        top_hit = hits[0]
        label = top_hit.get("label", mention)
        if not _overlaps_normalized(mention, label):
            return None
        return {
            "qid": top_hit.get("id", ""),
            "label": label,
            "description": top_hit.get("description", ""),
        }


class RealQueryRewriteAPI:
    """Deterministic query rewrite using query analysis.

    This is intentionally lightweight and reproducible for benchmarks. In
    production, this can be replaced by an LLM or a trained query-rewrite model.
    """

    STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "based",
        "by",
        "did",
        "does",
        "for",
        "from",
        "have",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }

    def should_rewrite(self, query: str, analysis: dict) -> bool:
        tokens = tokenize(query)
        intents = set(analysis.get("intents", []))
        if len(tokens) >= 12:
            return True
        if intents & {"compare", "metrics", "mechanics", "decision_support"}:
            return True
        if any(token.isdigit() for token in tokens):
            return True
        if len(analysis.get("noun_chunks", [])) >= 3:
            return True
        return False

    def rewrite(
        self,
        query: str,
        *,
        analysis: dict | None = None,
        linked_entities: list[dict | str] | None = None,
        max_rewrites: int = 3,
    ) -> dict:
        analysis = analysis or {}
        linked_entities = linked_entities or []

        rewrites = []
        entity_parts = []
        for item in linked_entities:
            if isinstance(item, dict):
                text = item.get("linked_text") or item.get("mention") or item.get("entity", "")
            else:
                text = str(item)
            if text:
                entity_parts.append(text)
        entity_text = " ".join(entity_parts).strip()
        if entity_text:
            rewrites.append(entity_text)

        noun_chunk_text = " ".join(analysis.get("noun_chunks", [])[:4]).strip()
        if noun_chunk_text:
            rewrites.append(noun_chunk_text)

        tokens = tokenize(query)
        keyword_tokens = [token for token in tokens if token not in self.STOPWORDS]
        if keyword_tokens:
            rewrites.append(" ".join(keyword_tokens[:12]))

        if len(tokens) >= 12:
            rewrites.append(" ".join(tokens[:10]))

        unique_rewrites = [item for item in _unique(rewrites) if item.lower() != query.lower()]
        return {
            "needed": self.should_rewrite(query, analysis),
            "rewrites": unique_rewrites[:max_rewrites],
            "method": "deterministic_query_rewrite",
        }


class RealHybridSearchAPI:
    """Hybrid BM25 + dense retrieval over indexed documents."""

    def __init__(
        self,
        documents: list[IndexedDocument],
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        *,
        batch_size: int = 64,
        local_files_only: bool = False,
    ) -> None:
        self.documents = documents
        self.embedding_model_name = embedding_model
        self.embedder = SentenceTransformer(embedding_model, local_files_only=local_files_only)
        self.texts = [doc.title + "\n" + doc.text for doc in documents]
        self.tokenized = [tokenize(text) for text in self.texts]
        self.bm25 = BM25Okapi(self.tokenized)
        embeddings = self.embedder.encode(
            self.texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        self.embeddings = np.asarray(embeddings, dtype=np.float32)

    def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        mode: str = "hybrid",
        bm25_weight: float = 0.55,
        include_doc_types: Iterable[str] | None = None,
        exclude_doc_types: Iterable[str] | None = None,
        include_sources: Iterable[str] | None = None,
        exclude_sources: Iterable[str] | None = None,
        must_terms: Iterable[str] | None = None,
        should_terms: Iterable[str] | None = None,
        exclude_terms: Iterable[str] | None = None,
    ) -> list[SearchCandidate]:
        mode = {"text": "bm25", "vector": "dense"}.get(mode, mode)
        if mode not in {"bm25", "dense", "hybrid"}:
            raise ValueError(f"Unsupported search mode: {mode}")
        bm25_weight = max(0.0, min(1.0, bm25_weight))

        if mode == "bm25":
            bm25_scores = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float32)
            dense_scores = np.zeros_like(bm25_scores, dtype=np.float32)
            bm25_norm = _minmax(bm25_scores)
            final = bm25_norm
        elif mode == "dense":
            bm25_scores = np.zeros(len(self.documents), dtype=np.float32)
            dense_query = self.embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            dense_scores = self.embeddings @ np.asarray(dense_query, dtype=np.float32)
            dense_norm = _minmax(dense_scores)
            final = dense_norm
        else:
            bm25_scores = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float32)
            dense_query = self.embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            dense_scores = self.embeddings @ np.asarray(dense_query, dtype=np.float32)
            bm25_norm = _minmax(bm25_scores)
            dense_norm = _minmax(dense_scores)
            final = bm25_weight * bm25_norm + (1.0 - bm25_weight) * dense_norm

        final = np.asarray(final, dtype=np.float32).copy()
        filtered_indices = self._filtered_indices(
            include_doc_types=include_doc_types,
            exclude_doc_types=exclude_doc_types,
            include_sources=include_sources,
            exclude_sources=exclude_sources,
            must_terms=must_terms,
            should_terms=should_terms,
            exclude_terms=exclude_terms,
        )
        if should_terms:
            should_tokens = _normalized_term_list(should_terms)
            for idx in filtered_indices:
                text = self.texts[int(idx)].lower()
                matched = sum(1 for term in should_tokens if term in text)
                if matched:
                    final[int(idx)] += min(0.18, 0.04 * matched)
        top_indices = sorted(filtered_indices, key=lambda idx: float(final[int(idx)]), reverse=True)[:top_k]
        candidates = []
        for idx in top_indices:
            doc = self.documents[int(idx)]
            candidates.append(
                SearchCandidate(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    text=doc.text,
                    metadata=doc.metadata,
                    score=float(final[idx]),
                    bm25_score=float(bm25_scores[idx]),
                    dense_score=float(dense_scores[idx]),
                )
            )
        return candidates

    def _filtered_indices(
        self,
        *,
        include_doc_types: Iterable[str] | None,
        exclude_doc_types: Iterable[str] | None,
        include_sources: Iterable[str] | None,
        exclude_sources: Iterable[str] | None,
        must_terms: Iterable[str] | None,
        should_terms: Iterable[str] | None,
        exclude_terms: Iterable[str] | None,
    ) -> list[int]:
        include_doc_types_set = set(_normalized_term_list(include_doc_types or []))
        exclude_doc_types_set = set(_normalized_term_list(exclude_doc_types or []))
        include_sources_set = set(_normalized_term_list(include_sources or []))
        exclude_sources_set = set(_normalized_term_list(exclude_sources or []))
        must_terms_list = _normalized_term_list(must_terms or [])
        exclude_terms_list = _normalized_term_list(exclude_terms or [])

        indices: list[int] = []
        for idx, doc in enumerate(self.documents):
            metadata = doc.metadata or {}
            doc_type = str(metadata.get("doc_type", "")).lower()
            source = str(metadata.get("source", "")).lower()
            if include_doc_types_set and doc_type not in include_doc_types_set:
                continue
            if exclude_doc_types_set and doc_type in exclude_doc_types_set:
                continue
            if include_sources_set and source not in include_sources_set:
                continue
            if exclude_sources_set and source in exclude_sources_set:
                continue
            text = self.texts[idx].lower()
            if must_terms_list and not all(term in text for term in must_terms_list):
                continue
            if exclude_terms_list and any(term in text for term in exclude_terms_list):
                continue
            indices.append(idx)
        return indices


class RealRankingAPI:
    """Cross-encoder reranking API."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        *,
        local_files_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.model = CrossEncoder(model_name, local_files_only=local_files_only)

    def rerank(
        self,
        query: str,
        candidates: Iterable[SearchCandidate | dict],
        *,
        top_k: int = 10,
    ) -> list[SearchCandidate]:
        candidates = [_coerce_candidate(candidate) for candidate in candidates]
        if not candidates:
            return []
        pairs = [(query, candidate.title + "\n" + candidate.text) for candidate in candidates]
        scores = self.model.predict(pairs, show_progress_bar=False)
        reranked = []
        for candidate, score in zip(candidates, scores):
            reranked.append(
                SearchCandidate(
                    doc_id=candidate.doc_id,
                    title=candidate.title,
                    text=candidate.text,
                    metadata={
                        **candidate.metadata,
                        "reranker_model": self.model_name,
                        "pre_rerank_score": candidate.score,
                    },
                    score=float(score),
                    bm25_score=candidate.bm25_score,
                    dense_score=candidate.dense_score,
                )
            )
        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked[:top_k]


def _coerce_candidate(candidate: SearchCandidate | dict) -> SearchCandidate:
    if isinstance(candidate, SearchCandidate):
        return candidate
    metadata = candidate.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    extras = {
        key: value
        for key, value in candidate.items()
        if key
        not in {
            "doc_id",
            "id",
            "title",
            "text",
            "metadata",
            "score",
            "bm25_score",
            "dense_score",
        }
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


def _minmax(scores: np.ndarray) -> np.ndarray:
    min_score = float(np.min(scores))
    max_score = float(np.max(scores))
    if math.isclose(max_score, min_score):
        return np.zeros_like(scores, dtype=np.float32)
    return (scores - min_score) / (max_score - min_score)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _normalized_term_list(items: Iterable[str] | str) -> list[str]:
    if isinstance(items, str):
        items = [items]
    return [str(item).lower().strip() for item in items if str(item).strip()]


def _overlaps_normalized(left: str, right: str) -> bool:
    left_norm = " ".join(tokenize(left))
    right_norm = " ".join(tokenize(right))
    if not left_norm or not right_norm:
        return False
    return left_norm in right_norm or right_norm in left_norm
