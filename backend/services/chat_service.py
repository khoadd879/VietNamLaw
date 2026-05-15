from services.gemini_service import generate_answer
from services.qdrant_service import search_legal_context
from services.session_service import get_session, save_message


def send_chat_message(db, session_id: str, user_id: str, message: str) -> tuple[str, list[str]]:
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    save_message(db, session_id, user_id, "user", message)

    contexts = search_legal_context(message)
    reply = generate_answer(message, contexts)
    sources = [item.get("source", "") for item in contexts if item.get("source")]

    save_message(db, session_id, user_id, "assistant", reply, {"sources": sources})

    return reply, sources