from qdrant_client import QdrantClient
import os


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "")
    )


def search_legal_context(message: str) -> list[dict[str, str]]:
    _ = message
    return []