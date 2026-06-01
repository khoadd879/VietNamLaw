from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from entities.chat_message import ChatMessage


def create_message(db: Session, message: ChatMessage) -> ChatMessage:
    db.add(message)
    db.commit()
    return message


def list_messages_for_session(db: Session, session_id: str) -> list[ChatMessage]:
    return db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    ).scalars().all()


def delete_messages_for_session(db: Session, session_id: str) -> None:
    db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    db.commit()


def list_recent_messages(db: Session, session_id: str, limit: int) -> list[ChatMessage]:
    """Return the most recent N messages ordered oldest -> newest."""
    all_msgs = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return list(reversed(all_msgs))