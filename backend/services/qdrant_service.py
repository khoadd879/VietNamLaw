import time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchText,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from core.config import (
    OLLAMA_EMBEDDING_MODEL,
    OLLAMA_URL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)


_EMBED_TIMEOUT_SECONDS = 300.0


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client configured from environment."""
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=300)


def ensure_collection_exists(client: QdrantClient) -> None:
    """Create collection if not exists with 1024 dims, cosine distance."""
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if QDRANT_COLLECTION_NAME in collection_names:
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )

    for field_name in ("topic_title", "demuc_title", "article_anchor", "source_url"):
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION_NAME,
            field_name=field_name,
            field_schema="keyword",
        )


def embed_texts(texts: list[str], task_type: str | None = None) -> list[list[float]]:
    """Embed texts via local Ollama model (e.g. bge-m3, 1024 dims).

    `task_type` is accepted for API compatibility but ignored — bge-m3 does not
    differentiate query vs document embeddings.
    """
    if not texts:
        return []

    url = f"{OLLAMA_URL.rstrip('/')}/api/embed"
    embeddings: list[list[float]] = []
    with httpx.Client(timeout=_EMBED_TIMEOUT_SECONDS) as client:
        for text in texts:
            response = client.post(
                url,
                json={"model": OLLAMA_EMBEDDING_MODEL, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            batch = data.get("embeddings") or ([data["embedding"]] if data.get("embedding") else [])
            if not batch:
                raise ValueError(f"Ollama returned no embedding for text: {text[:80]!r}")
            embeddings.append(batch[0])

    return embeddings


def ingest_articles(articles: list[dict], batch_size: int = 100) -> None:
    """Batch embed articles and upsert to Qdrant."""
    client = get_qdrant_client()

    texts = [article["content_text"] for article in articles]
    vectors = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    points = []
    for i, article in enumerate(articles):
        raw_id = str(article["id"])
        point_id = str(uuid5(NAMESPACE_URL, f"phapdien:{raw_id}"))
        point = PointStruct(
            id=point_id,
            vector=vectors[i],
            payload={
                "content_text": article["content_text"],
                "article_title": article["article_title"],
                "article_anchor": article["article_anchor"],
                "topic_title": article["topic_title"],
                "topic_id": article["topic_id"],
                "demuc_title": article["demuc_title"],
                "demuc_id": article["demuc_id"],
                "source_url": article["source_url"],
            },
        )
        points.append(point)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  [upsert retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
            time.sleep(wait)


def search_legal_context(
    message: str,
    filters: dict | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Embed message via Ollama, ANN search in Qdrant, return top results."""
    client = get_qdrant_client()

    vectors = embed_texts([message], task_type="RETRIEVAL_QUERY")
    query_vector = vectors[0]

    qdrant_filter = None
    if filters:
        conditions = []
        if filters.get("topic_title"):
            conditions.append(
                FieldCondition(
                    key="topic_title",
                    match=MatchText(text=filters["topic_title"]),
                )
            )
        if filters.get("demuc_title"):
            conditions.append(
                FieldCondition(
                    key="demuc_title",
                    match=MatchText(text=filters["demuc_title"]),
                )
            )
        if conditions:
            qdrant_filter = Filter(must=conditions)

    response = client.query_points(
        collection_name=QDRANT_COLLECTION_NAME,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
    )
    results: list[ScoredPoint] = list(response.points)

    return [
        {
            "content_text": point.payload.get("content_text", ""),
            "article_title": point.payload.get("article_title", ""),
            "source_url": point.payload.get("source_url", ""),
            "score": point.score,
        }
        for point in results
    ]
