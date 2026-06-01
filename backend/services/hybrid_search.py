"""Hybrid retrieval: vector (Qdrant) + BM25, normalized and weighted."""
import logging
import math
from typing import Any

from core.config import HYBRID_BM25_WEIGHT, HYBRID_VECTOR_WEIGHT
from services.bm25_index import load_index, search as bm25_search
from services.qdrant_service import search_legal_context as vector_search

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8


def _min_max_normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    s_min, s_max = min(scores), max(scores)
    if s_max == s_min:
        return [1.0 for _ in scores]
    return [(s - s_min) / (s_max - s_min) for s in scores]


def _dedupe_by_id(docs: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for d in docs:
        key = d.get("id") or d.get("doc_id")
        if key and key not in seen:
            seen[key] = d
    return list(seen.values())


def hybrid_search(
    query: str,
    filters: dict | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Run vector + BM25, combine scores, return top_k."""
    index = load_index()
    vector_results = vector_search(query, filters=filters, top_k=top_k * 2)
    bm25_results: list[dict] = []
    if index is not None:
        bm25, meta = index
        bm25_results = bm25_search(bm25, meta, query, top_k=top_k * 2)

    # Normalize each set to [0, 1]
    v_norm = _min_max_normalize([r.get("score", 0.0) for r in vector_results])
    b_norm = _min_max_normalize([r.get("bm25_score", 0.0) for r in bm25_results])

    vector_by_id: dict[str, tuple[dict, float]] = {}
    for r, s in zip(vector_results, v_norm):
        rid = r.get("id") or r.get("doc_id") or f"v{len(vector_by_id)}"
        vector_by_id[rid] = (r, s)

    bm25_by_id: dict[str, tuple[dict, float]] = {}
    for r, s in zip(bm25_results, b_norm):
        rid = r.get("id") or f"b{len(bm25_by_id)}"
        bm25_by_id[rid] = (r, s)

    all_ids = set(vector_by_id) | set(bm25_by_id)
    combined: list[dict] = []
    for rid in all_ids:
        v_doc, v_score = vector_by_id.get(rid, ({}, 0.0))
        b_doc, b_score = bm25_by_id.get(rid, ({}, 0.0))
        doc = {**(v_doc or b_doc)}
        doc["vector_score"] = v_score
        doc["bm25_normalized"] = b_score
        doc["score"] = HYBRID_VECTOR_WEIGHT * v_score + HYBRID_BM25_WEIGHT * b_score
        if rid in vector_by_id or rid in bm25_by_id:
            combined.append(doc)

    combined.sort(key=lambda d: d["score"], reverse=True)
    return _dedupe_by_id(combined)[:top_k]