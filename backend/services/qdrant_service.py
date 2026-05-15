from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    ScoredPoint,
    SearchParams,
    VectorSize,
)

from backend.core.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_URL,
)


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client configured from environment."""
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def ensure_collection_exists(client: QdrantClient) -> None:
    """Create collection if not exists with 768 dims, cosine distance."""
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if QDRANT_COLLECTION_NAME in collection_names:
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config=VectorSize(size=768, distance=Distance.COSINE),
    )

    # Create payload indexes for filtering
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="topic_title",
        field_schema="keyword",
    )
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="demuc_title",
        field_schema="keyword",
    )
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="article_anchor",
        field_schema="keyword",
    )
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="source_url",
        field_schema="keyword",
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts via Gemini embedding-001 API."""
    embeddings = []

    # Gemini batch embedding - process in chunks of 100 per API limit
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        response = GEMINI_API_KEY or ""
        if not response:
            raise ValueError("GEMINI_API_KEY not configured")

        # Import here to avoid circular import
        from google import genai

        client = genai.Client(api_key=response)

        batch_embeddings = []
        for text in batch:
            result = client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                content=text,
            )
            embedding = result.embeddings[0].values
            batch_embeddings.append(embedding)

        embeddings.extend(batch_embeddings)

    return embeddings


def ingest_articles(articles: list[dict], batch_size: int = 100) -> None:
    """Batch embed articles and upsert to Qdrant."""
    client = get_qdrant_client()

    # Prepare texts for embedding
    texts = [article["content_text"] for article in articles]

    # Batch embed
    vectors = embed_texts(texts)

    # Build points
    points = []
    for i, article in enumerate(articles):
        point = PointStruct(
            id=article["id"],
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

    # Upsert to Qdrant
    client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points)


def search_legal_context(
    message: str,
    filters: dict | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Embed message, ANN search in Qdrant, return top results with payload."""
    client = get_qdrant_client()

    # Embed query
    vectors = embed_texts([message])
    query_vector = vectors[0]

    # Build Qdrant filter
    qdrant_filter = None
    if filters:
        from qdrant_client.models import FieldCondition, MatchText, Filter

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

    # Search
    results: list[ScoredPoint] = client.search(
        collection_name=QDRANT_COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=qdrant_filter,
        limit=top_k,
        search_params=SearchParams(hnsw_algorithm=None),
    )

    # Format response
    formatted_results = []
    for point in results:
        formatted_results.append(
            {
                "content_text": point.payload.get("content_text", ""),
                "article_title": point.payload.get("article_title", ""),
                "source_url": point.payload.get("source_url", ""),
                "score": point.score,
            }
        )

    return formatted_results