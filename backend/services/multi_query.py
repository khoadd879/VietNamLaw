"""Generate 2-3 rephrasings of the user query to increase recall."""
import json
import logging

from core.config import MULTI_QUERY_COUNT

logger = logging.getLogger(__name__)

MULTI_QUERY_PROMPT = "multi_query_v1"


def expand_query(query: str, n_variants: int = 2) -> list[str]:
    """Stub expand_query - returns just the original query."""
    return [query]
