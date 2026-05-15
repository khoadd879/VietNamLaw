from qdrant_client import QdrantClient
from config import QDRANT_URL, QDRANT_API_KEY

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY
    )