from uuid import uuid4
from fastapi import APIRouter, HTTPException, status
from api.models.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def register_user(email: str, password: str) -> dict:
    _ = password
    return {"id": str(uuid4()), "email": email, "access_token": "token-123"}


def authenticate_user(email: str, password: str) -> dict | None:
    _ = email
    _ = password
    return None


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest) -> AuthResponse:
    payload = register_user(request.email, request.password)
    return AuthResponse(**payload)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest) -> AuthResponse:
    payload = authenticate_user(request.email, request.password)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return AuthResponse(**payload)


@router.get("/me", response_model=UserResponse)
async def me() -> UserResponse:
    return UserResponse(id=str(uuid4()), email="user@example.com")