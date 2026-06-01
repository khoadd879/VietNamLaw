import logging

from services.crossref_walker import walk_relationships
from services.hybrid_search import hybrid_search
from services.multi_query import expand_query as multi_query_expand
from services.citation_verifier import verify_citations
from services.session_service import (
    add_fact,
    get_session,
    list_case_facts,
    save_message,
    update_session_case,
)
from services.two_stage_reasoner import two_stage_reason
from repositories.messages import list_recent_messages
from core.config import MULTI_QUERY_COUNT, RETRIEVAL_TOP_K

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
LOW_SCORE_THRESHOLD = 0.30  # hybrid scores are normalized 0-1, so 0.30 is low


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


def _multi_query_retrieve(
    message: str,
    filters: dict | None,
    top_k: int,
) -> list[dict]:
    """Run multi-query expansion + hybrid search, then dedupe and merge."""
    queries = multi_query_expand(message, n_variants=MULTI_QUERY_COUNT)
    logger.info("multi_query: %d variants for session", len(queries))
    seen: dict[str, dict] = {}
    for q in queries:
        for chunk in hybrid_search(q, filters=filters, top_k=top_k):
            cid = chunk.get("id") or chunk.get("doc_id")
            if cid is None:
                continue
            if cid not in seen or chunk.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = chunk
    merged = list(seen.values())
    merged.sort(key=lambda c: c.get("score", 0), reverse=True)
    return merged[:top_k]


def _persist_extracted_facts(db, session_id, user_id, source_message_id, extracted):
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


def _persist_case_update(db, session_id, user_id, case_type, case_summary, *, mark_intake_complete=False):
    from datetime import datetime, timezone
    update_session_case(
        db, session_id=session_id, user_id=user_id,
        case_type=case_type, case_summary=case_summary,
        conversation_phase="consulting" if mark_intake_complete else None,
        intake_completed_at=datetime.now(timezone.utc) if mark_intake_complete else None,
    )


def send_chat_message(db, session_id, user_id, message) -> tuple[str, list[str], dict | None, dict | None]:
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    user_msg = save_message(db, session_id, user_id, "user", message)

    recent = list_recent_messages(db, session_id, limit=HISTORY_LIMIT)
    history = _format_history_for_llm(recent[:-1])

    existing_facts = list_case_facts(db, session_id)

    # SPRINT 3: hybrid + multi-query retrieval
    contexts = _multi_query_retrieve(message, filters=None, top_k=RETRIEVAL_TOP_K)

    # SPRINT 3: cross-ref walker
    if contexts:
        related = walk_relationships(contexts)
        # Dedupe against existing contexts
        seen_ids = {c.get("id") or c.get("doc_id") for c in contexts}
        for r in related:
            rid = r.get("id") or r.get("doc_id")
            if rid and rid not in seen_ids:
                contexts.append(r)
                seen_ids.add(rid)

    if not _is_retrieval_reliable(contexts):
        logger.info("Retrieval unreliable for session=%s", session_id)

    try:
        result = two_stage_reason(
            message=message, contexts=contexts, history=history,
            existing_facts=existing_facts,
            case_type=getattr(session, "case_type", None),
            case_summary=getattr(session, "case_summary", None),
        )
    except ValueError as exc:
        logger.warning("Two-stage failed: %s", exc)
        from services.groq_service import generate_answer
        text = generate_answer(question=message, contexts=contexts, history=history)
        save_message(db, session_id, user_id, "assistant", text, {"sources": []})
        return text, [], None, None

    structured = result["structured"]

    # SPRINT 3: verify citations against retrieved contexts
    structured = verify_citations(structured, contexts)

    _persist_extracted_facts(db, session_id, user_id, user_msg.id, result["extracted"])
    _persist_case_update(
        db, session_id, user_id,
        case_type=result.get("updated_case_type"),
        case_summary=result.get("updated_case_summary"),
        mark_intake_complete=bool(result["extracted"].get("extracted_facts")),
    )

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
