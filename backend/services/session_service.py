from datetime import datetime
from uuid import uuid4
from entities.chat_message import ChatMessage
from entities.chat_session import ChatSession
from repositories.messages import create_message, list_messages_for_session
from repositories.sessions import (
    create_session as repo_create_session,
    delete_session_for_user,
    get_session_for_user,
    list_sessions_for_user,
)


def create_session(db, user_id: str, title: str | None = None) -> ChatSession:
    session = ChatSession(
        id=str(uuid4()),
        user_id=user_id,
        title=title or "Cuộc trò chuyện mới",
    )
    return repo_create_session(db, session)


def list_sessions(db, user_id: str) -> list[ChatSession]:
    return list_sessions_for_user(db, user_id)


def get_session(db, session_id: str, user_id: str) -> ChatSession | None:
    return get_session_for_user(db, session_id, user_id)


def rename_session(db, session_id: str, user_id: str, title: str) -> ChatSession | None:
    session = get_session_for_user(db, session_id, user_id)
    if session is None:
        return None
    session.title = title
    db.commit()
    db.refresh(session)
    return session


def delete_session(db, session_id: str, user_id: str) -> bool:
    session = get_session_for_user(db, session_id, user_id)
    if session is None:
        return False
    delete_session_for_user(db, session_id)
    return True


def get_messages(db, session_id: str) -> list[ChatMessage]:
    return list_messages_for_session(db, session_id)


def save_message(
    db,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    sources_json: dict | None = None,
) -> ChatMessage:
    import json
    message = ChatMessage(
        id=str(uuid4()),
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
        sources_json=json.dumps(sources_json) if sources_json else None,
    )
    return create_message(db, message)


def get_or_create_session(db, user_id: str, title: str | None = None) -> ChatSession:
    """Alias for create_session; clearer name for intake flow."""
    return create_session(db, user_id, title)


def update_session_case(
    db,
    session_id: str,
    user_id: str,
    case_type: str | None = None,
    case_summary: str | None = None,
    conversation_phase: str | None = None,
    intake_completed_at: datetime | None = None,
) -> ChatSession | None:
    session = get_session_for_user(db, session_id, user_id)
    if session is None:
        return None
    if case_type is not None:
        session.case_type = case_type
    if case_summary is not None:
        session.case_summary = case_summary
    if conversation_phase is not None:
        session.conversation_phase = conversation_phase
    if intake_completed_at is not None:
        session.intake_completed_at = intake_completed_at
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def add_fact(
    db,
    session_id: str,
    user_id: str,
    fact_key: str,
    fact_value: str,
    source_message_id: str | None = None,
    confidence: float = 1.0,
):
    from entities.case_fact import CaseFact
    now = datetime.utcnow()
    fact = CaseFact(
        id=str(uuid4()),
        session_id=session_id,
        user_id=user_id,
        fact_key=fact_key,
        fact_value=fact_value,
        source_message_id=source_message_id,
        confidence=confidence,
        created_at=now,
        updated_at=now,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return fact


def list_case_facts(db, session_id: str):
    from entities.case_fact import CaseFact
    from sqlalchemy import select
    return db.execute(
        select(CaseFact).where(CaseFact.session_id == session_id).order_by(CaseFact.created_at.asc())
    ).scalars().all()