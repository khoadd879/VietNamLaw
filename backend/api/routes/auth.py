from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db
from dto.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from entities.user import User
from repositories.users import get_user_by_email
from services.auth_service import authenticate_user, create_token_for_user, register_user as svc_register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = get_user_by_email(db, request.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = svc_register_user(db, request.email, request.password)
    token = create_token_for_user(user)
    return AuthResponse(id=str(user.id), email=user.email, access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = authenticate_user(db, request.email, request.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_token_for_user(user)
    return AuthResponse(id=str(user.id), email=user.email, access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=str(current_user.id), email=current_user.email)