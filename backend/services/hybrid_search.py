"""Hybrid retrieval: vector (Qdrant) + BM25, normalized and weighted."""
import logging
from typing import Any

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
    """Stub hybrid_search - returns empty list."""
    return []
