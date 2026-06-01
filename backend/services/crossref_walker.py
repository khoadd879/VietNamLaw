"""Follow relationships[] in chunk payload to fetch related chunks."""
import logging
from typing import Any

from core.config import CROSSREF_MAX_CHUNKS, CROSSREF_MAX_HOPS
from services.qdrant_service import get_qdrant_client, QDRANT_COLLECTION_NAME

logger = logging.getLogger(__name__)


def _fetch_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    client = get_qdrant_client()
    from qdrant_client.http import models
    try:
        points = client.retrieve(
            collection_name=QDRANT_COLLECTION_NAME,
            ids=ids,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        logger.warning("crossref retrieve failed: %s", exc)
        return []
    out = []
    for p in points:
        out.append({
            "id": str(p.id),
            "content_text": p.payload.get("content_text", ""),
            "title": p.payload.get("title", ""),
            "article_label": p.payload.get("article_label"),
            "chapter_label": p.payload.get("chapter_label"),
            "loai_van_ban": p.payload.get("loai_van_ban", ""),
            "source_url": p.payload.get("source_url", ""),
            "score": 0.0,
        })
    return out


def walk_relationships(
    seed_chunks: list[dict[str, Any]],
    max_hops: int = CROSSREF_MAX_HOPS,
    max_chunks: int = CROSSREF_MAX_CHUNKS,
) -> list[dict[str, Any]]:
    """Given retrieved chunks, follow their relationships[] to gather more.

    Returns list of related chunks (NOT including the seeds). Capped at max_chunks.
    """
    seen_ids: set[str] = {str(c.get("id") or c.get("doc_id")) for c in seed_chunks if c.get("id") or c.get("doc_id")}
    queue: list[tuple[str, int]] = [
        (str(c.get("id") or c.get("doc_id")), 0)
        for c in seed_chunks
        if c.get("id") or c.get("doc_id")
    ]
    collected: list[dict[str, Any]] = []
    while queue and len(collected) < max_chunks:
        current_id, hop = queue.pop(0)
        if hop >= max_hops:
            continue
        # We don't have the full seed payload here; fetch by id to get relationships
        details = _fetch_by_ids([current_id])
        if not details:
            continue
        rel_ids: list[str] = details[0].get("content_text", "")  # placeholder
        # Re-fetch the actual seed to read relationships
        seeds_with_payload = [s for s in seed_chunks if str(s.get("id") or s.get("doc_id")) == current_id]
        if not seeds_with_payload:
            continue
        rels = seeds_with_payload[0].get("relationships") or []
        for rel in rels:
            target_id = rel.get("target_id") if isinstance(rel, dict) else str(rel)
            if not target_id or target_id in seen_ids:
                continue
            seen_ids.add(target_id)
            queue.append((target_id, hop + 1))
            if len(collected) < max_chunks:
                collected.append({"id": target_id, "_pending": True})
    # Fetch full payloads for pending entries
    pending_ids = [c["id"] for c in collected if c.get("_pending")]
    full = _fetch_by_ids(pending_ids)
    return full[:max_chunks]