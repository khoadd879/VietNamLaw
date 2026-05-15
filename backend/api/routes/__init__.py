from fastapi import APIRouter
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.sessions import router as sessions_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(sessions_router)

__all__ = ["router"]