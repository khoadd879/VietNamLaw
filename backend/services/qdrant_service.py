from qdrant_client import QdrantClient
from core.config import QDRANT_API_KEY, QDRANT_URL


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def search_legal_context(message: str) -> list[dict[str, str]]:
    _ = message
    return []