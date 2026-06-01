"""Two-stage reasoning: extract facts first, then synthesize with case brief."""
import json
import logging
from typing import Any

from services.fact_extractor import extract_facts
from services.groq_service import _run_pooled
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

SYNTHESIZER_PROMPT = "synthesizer_v1"


def _build_case_brief(case_type: str | None, case_summary: str | None, facts: list) -> dict:
    return {
        "case_type": case_type,
        "case_summary": case_summary,
        "facts": [{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in facts],
    }


def _format_case_brief_for_llm(brief: dict) -> str:
    lines = ["CASE_BRIEF:"]
    lines.append(f"- case_type: {brief['case_type'] or '(chưa rõ)'}")
    lines.append(f"- case_summary: {brief['case_summary'] or '(chưa có)'}")
    if brief["facts"]:
        lines.append("- facts:")
        for f in brief["facts"]:
            lines.append(f"    {f['key']}: {f['value']} (confidence={f['confidence']:.2f})")
    else:
        lines.append("- facts: (rỗng)")
    return "\n".join(lines)


def _format_context_chunks(contexts: list[dict]) -> list[str]:
    return [
        f"[{c.get('title', 'Văn bản pháp luật')}]\n{c.get('content_text', '')}"
        for c in contexts
    ]


def _build_synth_user_message(case_brief: dict, contexts: list[dict], question: str) -> str:
    parts = [_format_case_brief_for_llm(case_brief), ""]
    parts.append("NGỮ CẢNH PHÁP LÝ:")
    chunks = _format_context_chunks(contexts)
    if chunks:
        parts.extend(chunks)
    else:
        parts.append("(rỗng — không tìm thấy điều luật phù hợp, hãy hỏi user thêm facts)")
    parts.append("")
    parts.append("CÂU HỎI / YÊU CẦU TƯ VẤN HIỆN TẠI:")
    parts.append(question)
    return "\n".join(parts)


def two_stage_reason(
    message: str,
    contexts: list[dict],
    history: list[dict[str, str]] | None,
    existing_facts: list,
    case_type: str | None,
    case_summary: str | None,
) -> dict:
    """Stage 1: extract facts. Stage 2: synthesize using updated case brief.

    Returns dict with keys: structured, extracted, updated_case_type, updated_case_summary.
    Does NOT persist anything — caller (chat_service) does that.
    """
    # Stage 1
    extracted = extract_facts(
        message=message,
        existing_facts=[
            {"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence}
            for f in existing_facts
        ],
        case_type_hint=case_type,
    )

    # Build a virtual case brief (NOT yet persisted)
    virtual_brief = _build_case_brief(
        case_type=extracted.get("case_type") or case_type,
        case_summary=extracted.get("case_summary") or case_summary,
        facts=list(existing_facts) + [
            # Pseudo-fact objects for the LLM (not persisted)
            type("PF", (), {
                "fact_key": f["key"], "fact_value": f["value"], "confidence": f["confidence"]
            })()
            for f in extracted.get("extracted_facts", [])
        ],
    )

    # Stage 2
    system_prompt = load_prompt(SYNTHESIZER_PROMPT)
    user_text = _build_synth_user_message(virtual_brief, contexts, message)
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    raw = _run_pooled(messages, response_format={"type": "json_object"}, empty_fallback="")
    if not raw:
        raise ValueError("Synthesizer returned empty")
    structured = json.loads(raw)

    return {
        "structured": structured,
        "extracted": extracted,
        "updated_case_type": extracted.get("case_type") or case_type,
        "updated_case_summary": extracted.get("case_summary") or case_summary,
    }