import logging

from services.groq_service import generate_answer
from services.qdrant_service import search_legal_context
from services.session_service import (
    add_fact,
    get_session,
    list_case_facts,
    save_message,
    update_session_case,
)
from services.two_stage_reasoner import two_stage_reason
from repositories.messages import list_recent_messages

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
RETRIEVAL_TOP_K = 4
LOW_SCORE_THRESHOLD = 0.55


def _format_history_for_llm(messages) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _structured_to_display_text(structured: dict) -> str:
    parts: list[str] = []
    if structured.get("loi_chao"):
        parts.append(f"**{structured['loi_chao']}**\n")
    if structured.get("tom_tat_vu_viec"):
        parts.append(f"### Tóm tắt vụ việc\n{structured['tom_tat_vu_viec']}\n")
    if structured.get("phan_tich_phap_ly"):
        parts.append(f"### Phân tích pháp lý\n{structured['phan_tich_phap_ly']}\n")
    if structured.get("phuong_an_khuyen_nghi"):
        parts.append("### Phương án khuyến nghị")
        parts.extend(f"- {p}" for p in structured["phuong_an_khuyen_nghi"])
        parts.append("")
    if structured.get("rui_ro_can_luu_y"):
        parts.append("### Rủi ro cần lưu ý")
        parts.extend(f"- {r}" for r in structured["rui_ro_can_luu_y"])
        parts.append("")
    if structured.get("cau_hoi_hoi_them"):
        parts.append("### Câu hỏi cần bạn cung cấp thêm")
        parts.extend(f"- {c}" for c in structured["cau_hoi_hoi_them"])
        parts.append("")
    if structured.get("disclaimer"):
        parts.append(f"> ⚠️ {structured['disclaimer']}")
    return "\n".join(parts).strip()


def _is_retrieval_reliable(contexts: list[dict]) -> bool:
    if not contexts:
        return False
    if any(c.get("score", 1.0) < LOW_SCORE_THRESHOLD for c in contexts):
        return False
    return True


def _persist_extracted_facts(
    db,
    session_id: str,
    user_id: str,
    source_message_id: str,
    extracted: dict,
) -> None:
    for fact in extracted.get("extracted_facts", []) or []:
        if not fact.get("key") or fact.get("value") is None:
            continue
        add_fact(
            db,
            session_id=session_id,
            user_id=user_id,
            fact_key=fact["key"],
            fact_value=str(fact["value"]),
            source_message_id=source_message_id,
            confidence=float(fact.get("confidence", 1.0)),
        )


def _persist_case_update(
    db,
    session_id: str,
    user_id: str,
    case_type: str | None,
    case_summary: str | None,
    *,
    mark_intake_complete: bool = False,
) -> None:
    from datetime import datetime, timezone
    update_session_case(
        db,
        session_id=session_id,
        user_id=user_id,
        case_type=case_type,
        case_summary=case_summary,
        conversation_phase="consulting" if mark_intake_complete else None,
        intake_completed_at=datetime.now(timezone.utc) if mark_intake_complete else None,
    )


def send_chat_message(
    db,
    session_id: str,
    user_id: str,
    message: str,
) -> tuple[str, list[str], dict | None, dict | None]:
    """Main chat entry point.

    Returns (display_text, sources, structured, case_brief).
    """
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    # 1. Persist user turn first
    user_msg = save_message(db, session_id, user_id, "user", message)

    # 2. Load recent history
    recent = list_recent_messages(db, session_id, limit=HISTORY_LIMIT)
    history = _format_history_for_llm(recent[:-1])

    # 3. Load existing case facts
    existing_facts = list_case_facts(db, session_id)

    # 4. Retrieve legal context
    contexts = search_legal_context(message, top_k=RETRIEVAL_TOP_K)
    if not _is_retrieval_reliable(contexts):
        logger.info("Retrieval unreliable for session=%s", session_id)

    # 5. Two-stage reason
    try:
        result = two_stage_reason(
            message=message,
            contexts=contexts,
            history=history,
            existing_facts=existing_facts,
            case_type=getattr(session, "case_type", None),
            case_summary=getattr(session, "case_summary", None),
        )
    except ValueError as exc:
        logger.warning("Two-stage failed: %s", exc)
        text = generate_answer(question=message, contexts=contexts, history=history)
        save_message(db, session_id, user_id, "assistant", text, {"sources": []})
        return text, [], None, None

    structured = result["structured"]
    extracted = result["extracted"]

    # 6. Persist extracted facts
    _persist_extracted_facts(db, session_id, user_id, user_msg.id, extracted)

    # 7. Persist case_type / case_summary update; mark intake complete if we got facts
    _persist_case_update(
        db,
        session_id,
        user_id,
        case_type=result.get("updated_case_type"),
        case_summary=result.get("updated_case_summary"),
        mark_intake_complete=bool(extracted.get("extracted_facts")),
    )

    # 8. Render display text
    display = _structured_to_display_text(structured)
    # Only surface sources the LLM actually cited. If trich_dan_nguon is empty
    # (e.g. retrieval was unreliable and the LLM correctly refused to invent
    # citations), don't dump raw context URLs that aren't tied to any specific
    # article — they look authoritative but mean nothing to the user.
    cited_sources: list[str] = []
    if structured.get("trich_dan_nguon"):
        cited_sources = [c.get("source_url", "") for c in contexts if c.get("source_url")]
    case_brief = {
        "case_type": result.get("updated_case_type"),
        "case_summary": result.get("updated_case_summary"),
        "facts": [{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in existing_facts],
    }
    save_message(
        db, session_id, user_id, "assistant", display,
        {"sources": cited_sources, "structured": structured, "case_brief": case_brief},
    )
    return display, cited_sources, structured, case_brief