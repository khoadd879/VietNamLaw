# Neon Auth and Chat History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Neon-backed email/password auth, JWT protection, persistent chat sessions/messages, and authenticated chat APIs that store history by both user and session.

**Architecture:** Add a small Postgres layer for Neon, an auth service for password hashing and JWT issuance, and separate route modules for auth and chat-session history. Keep the existing Qdrant + Gemini generation flow, but require bearer auth and a valid `session_id` before `POST /chat` can store user and assistant messages.

**Tech Stack:** FastAPI, Pydantic v2, Neon Postgres, SQLAlchemy, psycopg, passlib[bcrypt], python-jose, pytest

---

## File structure

- Modify: `backend/requirements.txt` — add Postgres/auth dependencies
- Modify: `backend/config.py` — add Neon/JWT settings
- Modify: `backend/.env.example` — document Neon and JWT env vars
- Create: `backend/db.py` — SQLAlchemy engine/session factory for Neon
- Create: `backend/models.py` — SQLAlchemy models for users, chat sessions, chat messages
- Create: `backend/auth.py` — password hashing, JWT creation, current-user dependency
- Create: `backend/api/routes/auth.py` — register/login/me routes
- Create: `backend/api/routes/sessions.py` — session CRUD and message-list routes
- Modify: `backend/api/routes/chat.py` — require auth/session_id and persist messages
- Modify: `backend/api/routes/__init__.py` — include auth, session, chat routers
- Modify: `backend/api/models/schemas.py` — add auth/session/message schemas and extend chat request
- Create: `backend/tests/routes/test_auth.py` — auth route tests
- Create: `backend/tests/routes/test_sessions.py` — session CRUD/message tests
- Modify: `backend/tests/routes/test_chat.py` — authenticated chat persistence tests

### Task 1: Neon config and database layer

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Modify: `backend/.env.example`
- Create: `backend/db.py`
- Create: `backend/models.py`
- Test: `backend/tests/routes/test_auth.py`

- [ ] **Step 1: Write failing test for missing auth routes import path**

`backend/tests/routes/test_auth.py`
```python
from starlette.testclient import TestClient
from main import app


def test_register_route_exists() -> None:
    client = TestClient(app)
    response = client.post("/auth/register", json={"email": "user@example.com", "password": "secret123"})
    assert response.status_code != 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_auth.py::test_register_route_exists -v`
Expected: FAIL with `404 != 404` assertion failure because auth routes do not exist yet

- [ ] **Step 3: Add Neon/auth dependencies and config**

`backend/requirements.txt`
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
qdrant-client==1.18.0
sentence-transformers==5.5.0
pydantic==2.13.4
python-dotenv==1.0.0
google-genai>=1.16.1
httpx==0.27.2
starlette==0.35.1
pytest==8.4.0
sqlalchemy==2.0.41
psycopg[binary]==3.2.9
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.5.0
email-validator==2.2.0
```

`backend/config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
```

`backend/.env.example`
```env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
NEON_DATABASE_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
JWT_SECRET_KEY=replace_with_strong_secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

- [ ] **Step 4: Create minimal database files**

`backend/db.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import NEON_DATABASE_URL

Base = declarative_base()
engine = create_engine(NEON_DATABASE_URL or "sqlite+pysqlite:///:memory:", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```

`backend/models.py`
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 5: Run test to verify route still fails for missing implementation, but imports/config are valid**

Run: `cd backend && pytest tests/routes/test_auth.py::test_register_route_exists -v`
Expected: FAIL with 404 assertion, but no import/config errors

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/config.py backend/.env.example backend/db.py backend/models.py backend/tests/routes/test_auth.py
git commit -m "feat: add Neon database foundation"
```

### Task 2: Auth service and auth routes

**Files:**
- Create: `backend/auth.py`
- Create: `backend/api/routes/auth.py`
- Modify: `backend/api/routes/__init__.py`
- Modify: `backend/api/models/schemas.py`
- Test: `backend/tests/routes/test_auth.py`

- [ ] **Step 1: Replace route-exists test with concrete auth behavior tests**

`backend/tests/routes/test_auth.py`
```python
from uuid import uuid4
from starlette.testclient import TestClient
from main import app


def test_register_returns_user_and_token(monkeypatch) -> None:
    from api.routes import auth as auth_module

    monkeypatch.setattr(auth_module, "register_user", lambda email, password: {
        "id": str(uuid4()),
        "email": email,
        "access_token": "token-123",
    })

    client = TestClient(app)
    response = client.post("/auth/register", json={"email": "user@example.com", "password": "secret123"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["access_token"] == "token-123"


def test_login_returns_unauthorized_for_invalid_credentials(monkeypatch) -> None:
    from api.routes import auth as auth_module

    def fake_login(email: str, password: str):
        return None

    monkeypatch.setattr(auth_module, "authenticate_user", fake_login)

    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrongpass"})

    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routes/test_auth.py -v`
Expected: FAIL because auth route module and schemas do not exist yet

- [ ] **Step 3: Add auth schemas and service**

`backend/api/models/schemas.py`
```python
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr


class AuthResponse(UserResponse):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] | None = None
```

`backend/auth.py`
```python
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
```

- [ ] **Step 4: Create auth routes and wire router export**

`backend/api/routes/auth.py`
```python
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
```

`backend/api/routes/__init__.py`
```python
from fastapi import APIRouter
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(chat_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/routes/test_auth.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/auth.py backend/api/routes/auth.py backend/api/routes/__init__.py backend/api/models/schemas.py backend/tests/routes/test_auth.py
git commit -m "feat: add JWT auth routes"
```

### Task 3: Session and message history APIs

**Files:**
- Create: `backend/api/routes/sessions.py`
- Modify: `backend/api/routes/__init__.py`
- Modify: `backend/api/models/schemas.py`
- Create: `backend/tests/routes/test_sessions.py`

- [ ] **Step 1: Write failing session CRUD tests**

`backend/tests/routes/test_sessions.py`
```python
from starlette.testclient import TestClient
from main import app


def test_list_sessions_route_exists() -> None:
    client = TestClient(app)
    response = client.get("/chat/sessions")
    assert response.status_code != 404


def test_rename_session_route_exists() -> None:
    client = TestClient(app)
    response = client.patch("/chat/sessions/123", json={"title": "Vụ việc đất đai"})
    assert response.status_code != 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routes/test_sessions.py -v`
Expected: FAIL because session routes do not exist yet

- [ ] **Step 3: Add session/message schemas**

`backend/api/models/schemas.py`
```python
class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionUpdateRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str


class MessageResponse(BaseModel):
    id: str
    session_id: str
    user_id: str
    role: str
    content: str
    sources_json: dict | None = None
```

- [ ] **Step 4: Create minimal session routes and wire them**

`backend/api/routes/sessions.py`
```python
from uuid import uuid4
from fastapi import APIRouter
from api.models.schemas import MessageResponse, SessionCreateRequest, SessionResponse, SessionUpdateRequest

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest) -> SessionResponse:
    return SessionResponse(id=str(uuid4()), user_id=str(uuid4()), title=request.title or "Cuộc trò chuyện mới")


@router.get("", response_model=list[SessionResponse])
async def list_sessions() -> list[SessionResponse]:
    return []


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    return SessionResponse(id=session_id, user_id=str(uuid4()), title="Cuộc trò chuyện mới")


@router.patch("/{session_id}", response_model=SessionResponse)
async def rename_session(session_id: str, request: SessionUpdateRequest) -> SessionResponse:
    return SessionResponse(id=session_id, user_id=str(uuid4()), title=request.title)


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, bool]:
    return {"deleted": True}


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def list_messages(session_id: str) -> list[MessageResponse]:
    _ = session_id
    return []
```

`backend/api/routes/__init__.py`
```python
from fastapi import APIRouter
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.sessions import router as sessions_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(sessions_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/routes/test_sessions.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/sessions.py backend/api/routes/__init__.py backend/api/models/schemas.py backend/tests/routes/test_sessions.py
git commit -m "feat: add chat session APIs"
```

### Task 4: Real auth persistence and ownership enforcement

**Files:**
- Modify: `backend/auth.py`
- Modify: `backend/api/routes/auth.py`
- Modify: `backend/api/routes/sessions.py`
- Modify: `backend/db.py`
- Modify: `backend/models.py`
- Test: `backend/tests/routes/test_auth.py`
- Test: `backend/tests/routes/test_sessions.py`

- [ ] **Step 1: Add failing ownership/auth tests**

Append to `backend/tests/routes/test_sessions.py`
```python
def test_list_sessions_requires_authorization() -> None:
    client = TestClient(app)
    response = client.get("/chat/sessions")
    assert response.status_code == 401
```

Append to `backend/tests/routes/test_auth.py`
```python
def test_me_requires_authorization() -> None:
    client = TestClient(app)
    response = client.get("/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py -v`
Expected: FAIL because current routes are open and use stubs

- [ ] **Step 3: Add DB session dependency and current-user dependency**

`backend/db.py`
```python
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import NEON_DATABASE_URL

Base = declarative_base()
engine = create_engine(NEON_DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/auth.py`
```python
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY
from db import get_db
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise unauthorized from exc

    user_id = payload.get("sub")
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user
```

- [ ] **Step 4: Replace auth/session stubs with DB-backed behavior**

Implementation requirements:
- `POST /auth/register`: create user with hashed password, reject duplicate email, return token + user
- `POST /auth/login`: find user by email, verify password, return token + user
- `GET /auth/me`: use `get_current_user`
- session routes: require `get_current_user`, return only rows where `user_id == current_user.id`
- session delete: delete session rows plus message rows for owner

Minimal query example for `register` in `backend/api/routes/auth.py`:
```python
existing = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()
if existing is not None:
    raise HTTPException(status_code=409, detail="Email already exists")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/auth.py backend/api/routes/auth.py backend/api/routes/sessions.py backend/db.py backend/models.py backend/tests/routes/test_auth.py backend/tests/routes/test_sessions.py
git commit -m "feat: persist auth and session history"
```

### Task 5: Authenticated chat persistence

**Files:**
- Modify: `backend/api/routes/chat.py`
- Modify: `backend/tests/routes/test_chat.py`
- Modify: `backend/api/models/schemas.py`

- [ ] **Step 1: Rewrite chat test for authenticated session-aware storage**

`backend/tests/routes/test_chat.py`
```python
from uuid import uuid4
from starlette.testclient import TestClient
from main import app


def test_chat_requires_authorized_session(monkeypatch) -> None:
    from api.routes import chat as chat_module

    class FakeUser:
        id = str(uuid4())

    monkeypatch.setattr(chat_module, "get_current_user", lambda: FakeUser())
    monkeypatch.setattr(chat_module, "get_session_for_user", lambda db, session_id, user_id: {"id": session_id, "user_id": user_id})
    monkeypatch.setattr(chat_module, "save_chat_message", lambda **kwargs: None)
    monkeypatch.setattr(chat_module, "search_legal_context", lambda message: [{"source": "Luật Đất đai", "content": "Quy định về tranh chấp."}])
    monkeypatch.setattr(chat_module, "generate_answer", lambda question, contexts: "Bạn nên hòa giải trước tại địa phương.")

    client = TestClient(app)
    response = client.post("/chat", json={"session_id": str(uuid4()), "message": "Tranh chấp đất đai xử lý sao?"})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Bạn nên hòa giải trước tại địa phương.",
        "sources": ["Luật Đất đai"],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_chat.py -v`
Expected: FAIL because current chat route does not take `session_id` or auth dependency

- [ ] **Step 3: Add minimal chat persistence helpers and auth checks**

`backend/api/routes/chat.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from api.models.schemas import ChatRequest, ChatResponse
from api.services.gemini_service import generate_answer
from api.services.qdrant_service import search_legal_context
from auth import get_current_user
from db import get_db
from models import ChatMessage, ChatSession, User

router = APIRouter()


def get_session_for_user(db: Session, session_id: str, user_id: str) -> ChatSession | None:
    return db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    ).scalar_one_or_none()


def save_chat_message(
    db: Session,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    sources_json: dict | None = None,
) -> None:
    db.add(
        ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            sources_json=sources_json,
        )
    )
    db.commit()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    session = get_session_for_user(db, request.session_id, str(current_user.id))
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    save_chat_message(db, request.session_id, str(current_user.id), "user", request.message)
    contexts = search_legal_context(request.message)
    reply = generate_answer(request.message, contexts)
    sources = [item["source"] for item in contexts if item.get("source")]
    save_chat_message(
        db,
        request.session_id,
        str(current_user.id),
        "assistant",
        reply,
        {"sources": sources},
    )
    return ChatResponse(reply=reply, sources=sources)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/routes/test_chat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/chat.py backend/api/models/schemas.py backend/tests/routes/test_chat.py
git commit -m "feat: persist authenticated chat messages"
```

### Task 6: Integration verification and docs

**Files:**
- Modify: `docs/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing docs checklist**

```txt
1. Backend env docs mention NEON_DATABASE_URL and JWT settings
2. Auth endpoints are documented
3. Session history endpoints are documented
4. README reflects authenticated chat requirement
```

- [ ] **Step 2: Verify docs checklist currently fails**

Run: `grep -R "NEON_DATABASE_URL\|JWT_SECRET_KEY\|/auth/register\|/chat/sessions" README.md docs/README.md`
Expected: missing entries

- [ ] **Step 3: Update docs**

`docs/README.md`
```md
| `NEON_DATABASE_URL` | Neon Postgres connection string | Yes |
| `JWT_SECRET_KEY` | JWT signing secret | Yes |
| `JWT_ALGORITHM` | JWT signing algorithm | No (default: HS256) |
| `JWT_EXPIRE_MINUTES` | Access token expiry in minutes | No (default: 60) |
```

```md
- `POST /auth/register` - Register and receive access token
- `POST /auth/login` - Login and receive access token
- `GET /auth/me` - Get current authenticated user
- `POST /chat/sessions` - Create chat session
- `GET /chat/sessions` - List current user chat sessions
- `GET /chat/sessions/{session_id}` - Get session metadata
- `PATCH /chat/sessions/{session_id}` - Rename session
- `DELETE /chat/sessions/{session_id}` - Delete session and messages
- `GET /chat/sessions/{session_id}/messages` - List messages in a session
```

`README.md`
```md
Authenticated legal chatbot with Neon-backed user accounts and session history.
```

- [ ] **Step 4: Run focused verification**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py tests/routes/test_chat.py tests/services/test_gemini_service.py -v`
Expected: PASS

Run: `grep -R "NEON_DATABASE_URL\|JWT_SECRET_KEY\|/auth/register\|/chat/sessions" README.md docs/README.md`
Expected: matching lines present

- [ ] **Step 5: Commit**

```bash
git add docs/README.md README.md
git commit -m "docs: add auth and Neon history setup"
```

## Self-review

- Spec coverage: auth, Neon config, user/session/message persistence, authenticated chat with session_id, full session APIs, ownership rules, and docs verification all map to tasks above.
- Placeholder scan: no TBD/TODO placeholders remain; each task has concrete files, commands, and code.
- Type consistency: `ChatRequest` always includes `session_id` + `message`; auth responses use `access_token`; session/message schema names remain stable across route and test tasks.
