from fastapi import APIRouter
from api.models.schemas import ChatRequest, ChatResponse
from api.services.gemini_service import generate_answer
from api.services.qdrant_service import search_legal_context

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    contexts = search_legal_context(request.message)
    reply = generate_answer(request.message, contexts)
    sources = [item["source"] for item in contexts if item.get("source")]
    return ChatResponse(reply=reply, sources=sources)