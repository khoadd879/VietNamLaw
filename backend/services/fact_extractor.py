"""LLM-based fact extraction from user messages (placeholder for Task 2.4 integration)."""
import json
import logging
import re
from typing import Any

from services.groq_service import _run_pooled
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

FACT_EXTRACTOR_PROMPT = "fact_extractor_v1"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(s: str) -> str:
    return _FENCE_RE.sub("", s).strip()


def extract_facts(
    message: str,
    existing_facts: list[dict[str, Any]] | None = None,
    case_type_hint: str | None = None,
) -> dict:
    """Call LLM and return parsed JSON: {case_type, extracted_facts, case_summary}.

    Falls back to a safe empty result if the LLM returns invalid JSON.
    Never raises — extractor is best-effort.
    """
    system_prompt = load_prompt(FACT_EXTRACTOR_PROMPT)
    user_payload = {
        "existing_facts": existing_facts or [],
        "new_message": message,
        "case_type_hint": case_type_hint,
    }
    user_text = json.dumps(user_payload, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    raw = _run_pooled(
        messages,
        response_format={"type": "json_object"},
        empty_fallback="",
    )
    if not raw:
        return {"case_type": None, "extracted_facts": [], "case_summary": None}
    cleaned = _strip_code_fence(raw)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Fact extractor returned invalid JSON: %r (%s)", raw[:200], exc)
        return {"case_type": None, "extracted_facts": [], "case_summary": None}
    return {
        "case_type": result.get("case_type"),
        "extracted_facts": result.get("extracted_facts") or [],
        "case_summary": result.get("case_summary"),
    }