from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from api.models.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from auth import create_access_token, get_current_user, hash_password, verify_password
from db import get_db
from models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(id=str(uuid4()), email=request.email, password_hash=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id))
    return AuthResponse(id=str(user.id), email=user.email, access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return AuthResponse(id=str(user.id), email=user.email, access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=str(current_user.id), email=current_user.email)
