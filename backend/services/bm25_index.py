"""In-memory BM25 index over Qdrant collection, with disk persistence."""
import logging
import pickle
import re
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# Stub: BM25 implementation will be added by Task 3.1
# This stub allows Task 3.4 to import without errors

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def build_index() -> tuple:
    """Stub build_index - returns empty index."""
    return (None, [])


def load_index(path: str | None = None):
    """Stub load_index - returns None (index not built yet)."""
    return None


def save_index(bm25, corpus_meta, path: str | None = None) -> None:
    """Stub save_index - no-op."""
    pass


def search(bm25, corpus_meta, query, top_k: int = 10) -> list[dict]:
    """Stub search - returns empty list."""
    return []
