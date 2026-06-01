from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db
from dto.chat import IntakeRequest, IntakeResponse
from entities.user import User
from services.chat_service import send_chat_message
from services.session_service import (
    add_fact,
    list_case_facts,
    update_session_case,
)
from datetime import datetime

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] | None = None
    structured: dict | None = None
    case_brief: dict | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    try:
        reply, sources, structured, case_brief = send_chat_message(
            db, request.session_id, str(current_user.id), request.message
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ChatResponse(reply=reply, sources=sources, structured=structured, case_brief=case_brief)


@router.post("/chat/intake", response_model=IntakeResponse)
async def submit_intake(
    request: IntakeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntakeResponse:
    session = update_session_case(
        db,
        session_id=request.session_id,
        user_id=str(current_user.id),
        case_type=request.case_type,
        case_summary=request.case_summary,
        conversation_phase="consulting",
        intake_completed_at=datetime.utcnow(),
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    for fact in request.initial_facts:
        add_fact(
            db,
            session_id=request.session_id,
            user_id=str(current_user.id),
            fact_key=fact.key,
            fact_value=fact.value,
        )
    facts = list_case_facts(db, request.session_id)
    return IntakeResponse(
        session_id=request.session_id,
        case_type=session.case_type or "",
        case_summary=session.case_summary or "",
        facts=[{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in facts],
    )
