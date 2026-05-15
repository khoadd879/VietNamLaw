from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from dto.chat import ChatRequest, ChatResponse
from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db
from entities.user import User
from services.chat_service import send_chat_message

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    try:
        reply, sources = send_chat_message(db, request.session_id, str(current_user.id), request.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ChatResponse(reply=reply, sources=sources)