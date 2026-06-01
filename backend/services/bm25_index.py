"""In-memory BM25 index over Qdrant collection, with disk persistence."""
import logging
import pickle
import re
from pathlib import Path
from typing import Iterable

from rank_bm25 import BM25Okapi

from core.config import BM25_INDEX_PATH
from services.qdrant_service import get_qdrant_client, QDRANT_COLLECTION_NAME

logger = logging.getLogger(__name__)

# Vietnamese tokenization is hard; for Sprint 3 we use simple word split on
# whitespace + lowercase. This is good enough for matching exact article
# numbers ("Điều 51", "Khoản 2") and proper nouns. Future: integrate pyvi.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _scroll_all_points(batch_size: int = 200) -> Iterable[dict]:
    """Yield every point in the Qdrant collection as a dict."""
    client = get_qdrant_client()
    offset = None
    while True:
        result = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = result
        for point in points:
            yield {
                "id": str(point.id),
                "content_text": point.payload.get("content_text", ""),
                "title": point.payload.get("title", ""),
                "article_label": point.payload.get("article_label"),
                "chapter_label": point.payload.get("chapter_label"),
                "loai_van_ban": point.payload.get("loai_van_ban", ""),
                "source_url": point.payload.get("source_url", ""),
            }
        if next_offset is None:
            break
        offset = next_offset


def build_index() -> tuple[BM25Okapi, list[dict]]:
    """Build a fresh BM25 index from the current Qdrant collection.

    Returns (bm25, corpus_meta) where corpus_meta[i] corresponds to doc i.
    """
    corpus_meta: list[dict] = []
    tokenized_corpus: list[list[str]] = []
    for doc in _scroll_all_points():
        corpus_meta.append(doc)
        tokenized_corpus.append(_tokenize(doc["content_text"] + " " + doc.get("title", "")))
    bm25 = BM25Okapi(tokenized_corpus)
    logger.info("Built BM25 index with %d documents", len(corpus_meta))
    return bm25, corpus_meta


def save_index(bm25: BM25Okapi, corpus_meta: list[dict], path: str | None = None) -> None:
    target = Path(path or BM25_INDEX_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        pickle.dump({"bm25": bm25, "corpus_meta": corpus_meta}, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Saved BM25 index to %s", target)


def load_index(path: str | None = None) -> tuple[BM25Okapi, list[dict]] | None:
    target = Path(path or BM25_INDEX_PATH)
    if not target.is_file():
        return None
    with target.open("rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["corpus_meta"]


def search(bm25: BM25Okapi, corpus_meta: list[dict], query: str, top_k: int = 10) -> list[dict]:
    """Return top_k docs by BM25 score, formatted like qdrant_service returns."""
    tokens = _tokenize(query)
    scores = bm25.get_scores(tokens)
    # Pair (score, idx), sort desc, take top_k
    paired = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for idx, score in paired:
        meta = corpus_meta[idx]
        results.append({**meta, "score": float(score), "bm25_score": float(score)})
    return results