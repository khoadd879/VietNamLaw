from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from entities.case_fact import CaseFact
from entities.chat_message import ChatMessage
from entities.chat_session import ChatSession


def create_session(db: Session, session: ChatSession) -> ChatSession:
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions_for_user(db: Session, user_id: str) -> list[ChatSession]:
    return db.execute(
        select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
    ).scalars().all()


def get_session_for_user(db: Session, session_id: str, user_id: str) -> ChatSession | None:
    return db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    ).scalar_one_or_none()


def delete_session_for_user(db: Session, session_id: str) -> None:
    """Delete a session and all its child rows.

    Order matters: ``case_facts`` references both ``chat_messages`` and
    ``chat_sessions``, so facts must be removed first, then messages,
    then the session itself. Otherwise the FK constraint on
    ``chat_messages_session_id_fkey`` (and the one on ``case_facts``)
    will block the delete.
    """
    db.execute(delete(CaseFact).where(CaseFact.session_id == session_id))
    db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    db.commit()