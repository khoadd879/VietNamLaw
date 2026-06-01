"""Follow relationships[] in chunk payload to fetch related chunks."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def walk_relationships(
    seed_chunks: list[dict[str, Any]],
    max_hops: int = 1,
    max_chunks: int = 5,
) -> list[dict[str, Any]]:
    """Stub walk_relationships - returns empty list."""
    return []
