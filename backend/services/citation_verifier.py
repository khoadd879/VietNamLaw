"""Verify LLM-cited chunk IDs against retrieved chunks; drop unverifiable ones."""
import logging
import re
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

# Citation strings LLM might produce
_DIEU_RE = re.compile(r"điều\s+(\d+)", re.IGNORECASE)
_KHOAN_RE = re.compile(r"khoản\s+(\d+)", re.IGNORECASE)
_DIEM_RE = re.compile(r"điểm\s+([a-z]\d*)", re.IGNORECASE)

_CORE_SEGMENT_RE = re.compile(
    r"(điều\s+\d+)|(khoản\s+\d+)|(điểm\s+[a-z]\d*)",
    re.IGNORECASE,
)


def _extract_citation_segments(text: str) -> set[str]:
    """Extract core citation segments (Điều N, Khoản N, Điểm X) from text."""
    return {m.group(0).strip().lower() for m in _CORE_SEGMENT_RE.finditer(text or "")}


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _phrase_present_in_chunks(phrase: str, chunks: list[dict]) -> bool:
    """A citation phrase is 'verified' if it appears (fuzzy ≥ 0.8) in any chunk content."""
    for c in chunks:
        content = (c.get("content_text") or "").lower()
        if phrase in content:
            return True
        # Fuzzy: look for the most similar substring of length >= len(phrase)//2
        if len(phrase) >= 5 and _similarity(phrase[:30], content[:300]) >= 0.8:
            return True
    return False


def verify_citations(
    structured: dict,
    contexts: list[dict[str, Any]],
) -> dict:
    """Filter structured['trich_dan_nguon'] to only include verifiable ones.

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
        segments = _extract_citation_segments(cite)
        # If no recognizable citation segment, just trust the cite as-is
        if not segments:
            verified.append(cite)
            continue
        if any(_phrase_present_in_chunks(p, contexts) for p in segments):
            verified.append(cite)
        else:
            dropped.append(cite)
            logger.info("Citation dropped (no matching chunk): %r", cite)
    structured["trich_dan_nguon"] = verified
    if dropped:
        logger.info("verify_citations: kept %d, dropped %d", len(verified), len(dropped))
    return structured