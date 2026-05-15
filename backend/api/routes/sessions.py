from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from auth import get_current_user
from db import get_db
from models import ChatMessage, ChatSession, User
from api.models.schemas import MessageResponse, SessionCreateRequest, SessionResponse, SessionUpdateRequest

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = ChatSession(
        id=str(uuid4()),
        user_id=str(current_user.id),
        title=request.title or "Cuộc trò chuyện mới",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionResponse(id=str(session.id), user_id=str(session.user_id), title=session.title)


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    sessions = db.execute(
        select(ChatSession).where(ChatSession.user_id == str(current_user.id)).order_by(ChatSession.updated_at.desc())
    ).scalars().all()
    return [SessionResponse(id=str(s.id), user_id=str(s.user_id), title=s.title) for s in sessions]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == str(current_user.id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionResponse(id=str(session.id), user_id=str(session.user_id), title=session.title)


@router.patch("/{session_id}", response_model=SessionResponse)
async def rename_session(
    session_id: str,
    request: SessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == str(current_user.id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.title = request.title
    db.commit()
    db.refresh(session)
    return SessionResponse(id=str(session.id), user_id=str(session.user_id), title=session.title)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    session = db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == str(current_user.id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    db.commit()
    return {"deleted": True}


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageResponse]:
    session = db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == str(current_user.id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    ).scalars().all()
    return [
        MessageResponse(
            id=str(m.id),
            session_id=str(m.session_id),
            user_id=str(m.user_id),
            role=m.role,
            content=m.content,
            sources_json=m.sources_json,
        )
        for m in messages
    ]
