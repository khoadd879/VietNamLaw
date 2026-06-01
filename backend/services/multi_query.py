"""Generate 2-3 rephrasings of the user query to increase recall."""
import json
import logging

from services.groq_service import _run_pooled
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

MULTI_QUERY_PROMPT = "multi_query_v1"


def expand_query(query: str, n_variants: int = 2) -> list[str]:
    """Return original query + up to n_variants rephrasings.

    Falls back to [query] if LLM fails.
    """
    system_prompt = load_prompt(MULTI_QUERY_PROMPT)
    user_text = f"Câu hỏi: {query}\nSố biến thể cần sinh: {n_variants}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    raw = _run_pooled(messages, response_format={"type": "json_object"}, empty_fallback="")
    if not raw:
        return [query]
    try:
        data = json.loads(raw)
        queries = data.get("queries") or []
    except json.JSONDecodeError:
        logger.warning("multi_query returned invalid JSON: %r", raw[:200])
        return [query]
    # Always include the original
    out = [query]
    for q in queries:
        if q and q != query and q not in out:
            out.append(q)
        if len(out) >= n_variants + 1:
            break
    return out