import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory (where this file lives) regardless of CWD.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "legal_articles")
LEGAL_DATASET_NAME = os.getenv("LEGAL_DATASET_NAME", "th1nhng0/vietnamese-legal-documents")
LEGAL_DATASET_METADATA_CONFIG = os.getenv("LEGAL_DATASET_METADATA_CONFIG", "metadata")
LEGAL_DATASET_CONTENT_CONFIG = os.getenv("LEGAL_DATASET_CONTENT_CONFIG", "content")
LEGAL_DATASET_RELATIONSHIPS_CONFIG = os.getenv("LEGAL_DATASET_RELATIONSHIPS_CONFIG", "relationships")
LEGAL_DATASET_SPLIT = os.getenv("LEGAL_DATASET_SPLIT", "data")
LEGAL_CHUNK_MAX_CHARS = int(os.getenv("LEGAL_CHUNK_MAX_CHARS", "1500"))
GROQ_API_KEYS = [
    key.strip()
    for key in [
        os.getenv("GROQ_API_KEY_1", ""),
        os.getenv("GROQ_API_KEY_2", ""),
        os.getenv("GROQ_API_KEY_3", ""),
    ]
    if key.strip()
]
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3")
# bge-m3 saturates GPU at batch=256 (RTX 4060 8GB measured 142 items/s).
# Larger batches don't help — single-GPU bound.
OLLAMA_EMBED_BATCH_SIZE = int(os.getenv("OLLAMA_EMBED_BATCH_SIZE", "256"))
# Upsert batch to Qdrant Cloud: larger = fewer round-trips, ~4ms/pt @ 1000
INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "500"))
# Unused — kept for back-compat with existing scripts
INGEST_CONCURRENT_WORKERS = int(os.getenv("INGEST_CONCURRENT_WORKERS", "1"))
OLLAMA_EMBED_TIMEOUT = int(os.getenv("OLLAMA_EMBED_TIMEOUT", "300"))
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

BM25_INDEX_PATH = os.getenv("BM25_INDEX_PATH", "./data/bm25_index.pkl")
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.6"))
HYBRID_BM25_WEIGHT = float(os.getenv("HYBRID_BM25_WEIGHT", "0.4"))
MULTI_QUERY_COUNT = int(os.getenv("MULTI_QUERY_COUNT", "2"))
PHAPDIEN_MAX_CONTENT_CHARS = int(os.getenv("PHAPDIEN_MAX_CONTENT_CHARS", "10000"))
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "20"))
