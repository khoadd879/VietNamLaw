from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dto.session import MessageResponse, SessionCreateRequest, SessionResponse, SessionUpdateRequest
from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db
from entities.user import User
from services.session_service import (
    create_session as svc_create_session,
    delete_session as svc_delete_session,
    get_messages as svc_get_messages,
    get_session as svc_get_session,
    list_sessions as svc_list_sessions,
    rename_session as svc_rename_session,
)

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = svc_create_session(db, str(current_user.id), request.title)
    return SessionResponse(id=str(session.id), user_id=str(session.user_id), title=session.title)


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionResponse]:
    sessions = svc_list_sessions(db, str(current_user.id))
    return [SessionResponse(id=str(s.id), user_id=str(s.user_id), title=s.title) for s in sessions]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = svc_get_session(db, session_id, str(current_user.id))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(id=str(session.id), user_id=str(session.user_id), title=session.title)


@router.patch("/{session_id}", response_model=SessionResponse)
async def rename_session(
    session_id: str,
    request: SessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = svc_rename_session(db, session_id, str(current_user.id), request.title)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(id=str(session.id), user_id=str(session.user_id), title=session.title)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    deleted = svc_delete_session(db, session_id, str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageResponse]:
    session = svc_get_session(db, session_id, str(current_user.id))
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = svc_get_messages(db, session_id)
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