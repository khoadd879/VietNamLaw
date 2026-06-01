import logging

from services.answer_service import generate_answer
from services.groq_service import generate_structured_answer
from services.qdrant_service import search_legal_context
from services.session_service import get_session, save_message
from repositories.messages import list_recent_messages

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
RETRIEVAL_TOP_K = 4
LOW_SCORE_THRESHOLD = 0.55  # below this we treat retrieval as unreliable


def _format_history_for_llm(messages) -> list[dict]:
    """Convert ORM messages to plain dicts in OpenAI chat format."""
    return [{"role": m.role, "content": m.content} for m in messages]


def _structured_to_display_text(structured: dict) -> str:
    """Flatten the 7-section JSON into a user-friendly Markdown block for fallback/sources."""
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


def send_chat_message(
    db,
    session_id: str,
    user_id: str,
    message: str,
) -> tuple[str, list[str], dict | None]:
    """Main chat entry point used by the API route.

    Returns (display_text, sources, structured_dict_or_None).
    """
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    # 1. Persist user turn first
    save_message(db, session_id, user_id, "user", message)

    # 2. Load recent history (oldest -> newest) for context
    recent = list_recent_messages(db, session_id, limit=HISTORY_LIMIT)
    # Drop the message we just saved from the history we feed to the LLM
    history = _format_history_for_llm(recent[:-1])

    # 3. Retrieve legal context
    contexts = search_legal_context(message, top_k=RETRIEVAL_TOP_K)

    # 4. Guard: if retrieval is empty/unreliable, do NOT silently invent law.
    #    We still call the LLM with empty contexts; the system prompt instructs
    #    the LLM to ask for more facts and not invent citations.
    if not _is_retrieval_reliable(contexts):
        logger.info("Retrieval unreliable for session=%s msg=%r", session_id, message[:80])

    # 5. Try structured JSON path first
    structured: dict | None = None
    try:
        structured = generate_structured_answer(
            question=message, contexts=contexts, history=history
        )
    except ValueError as exc:
        logger.warning("Structured answer failed (%s), falling back to text", exc)
        text = generate_answer(question=message, contexts=contexts, history=history)
        save_message(db, session_id, user_id, "assistant", text, {"sources": []})
        return text, [], None

    # 6. Render display text from structured JSON
    display = _structured_to_display_text(structured)
    # Only surface sources the LLM actually cited. If trich_dan_nguon is empty
    # (e.g. retrieval was unreliable and the LLM correctly refused to invent
    # citations), don't dump raw context URLs that aren't tied to any specific
    # article — they look authoritative but mean nothing to the user.
    cited_sources: list[str] = []
    if structured.get("trich_dan_nguon"):
        cited_sources = [
            item.get("source_url", "")
            for item in contexts
            if item.get("source_url")
        ]
    save_message(
        db, session_id, user_id, "assistant", display,
        {"sources": cited_sources, "structured": structured},
    )
    return display, cited_sources, structured
