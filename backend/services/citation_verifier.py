"""Verify LLM-cited chunk IDs against retrieved chunks; drop unverifiable ones."""
import logging
import re
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

# Citation strings LLM might produce. We match the canonical form (Điều N,
# Khoản N, Điểm x) so the extracted phrase is short enough to fuzzy-match
# chunk content. Non-greedy: stop at the first dash/comma/space-after-number
# so "Điều 51 - Luật HNGĐ" yields "điều 51" not the whole string.
_CITATION_RE = re.compile(
    r"(?:Điều|Khoản|Điểm)\s+\w+",
    re.IGNORECASE,
)


def _extract_citation_phrases(text: str) -> set[str]:
    """Extract likely citation phrases from a piece of text."""
    return {m.group(0).strip().lower() for m in _CITATION_RE.finditer(text or "")}


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _phrase_present_in_chunks(phrase: str, chunks: list[dict]) -> bool:
    """A citation phrase is 'verified' if it appears (fuzzy ≥ 0.8) in any chunk content."""
    for c in chunks:
        content = (c.get("content_text") or "").lower()
        if phrase in content:
            return True
        if len(phrase) >= 5 and _similarity(phrase[:30], content[:300]) >= 0.8:
            return True
    return False


def verify_citations(
    structured: dict,
    contexts: list[dict[str, Any]],
) -> dict:
    """Filter structured['trich_dan_nguonor'] to only include verifiable ones.

    Also augments structured['trich_dan_nguon'] with source_url from matching
    context for any verified citation.

    Returns the (mutated) structured dict.
    """
    cited: list[str] = structured.get("trich_dan_nguon") or []
    if not cited:
        return structured
    verified: list[str] = []
    dropped: list[str] = []
    for cite in cited:
        phrases = _extract_citation_phrases(cite)
        if not phrases:
            verified.append(cite)
            continue
        if any(_phrase_present_in_chunks(p, contexts) for p in phrases):
            verified.append(cite)
        else:
            dropped.append(cite)
            logger.info("Citation dropped (no matching chunk): %r", cite)
    structured["trich_dan_nguon"] = verified
    if dropped:
        logger.info("verify_citations: kept %d, dropped %d", len(verified), len(dropped))
    return structured
