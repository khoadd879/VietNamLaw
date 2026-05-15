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