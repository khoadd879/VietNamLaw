# Backend Layered Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backend into explicit layers (`api`, `dependencies`, `core`, `db`, `entities`, `dto`, `repositories`, `services`) while preserving all verified auth, chat, session, Gemini, and Qdrant behavior.

**Architecture:** Keep FastAPI routes and endpoint contracts unchanged, but move configuration, security helpers, DB setup, ORM entities, DTOs, repositories, and business logic into separate modules. Clean mixed-responsibility files instead of merely moving them, so routes become thin and feature logic lives in services/repositories.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, psycopg, python-jose, passlib, pytest

---

## File structure

- Create: `backend/api/dependencies/auth.py`
- Create: `backend/api/dependencies/database.py`
- Create: `backend/core/config.py`
- Create: `backend/core/security.py`
- Create: `backend/db/base.py`
- Create: `backend/db/session.py`
- Create: `backend/db/init_db.py`
- Create: `backend/entities/user.py`
- Create: `backend/entities/chat_session.py`
- Create: `backend/entities/chat_message.py`
- Create: `backend/dto/auth.py`
- Create: `backend/dto/chat.py`
- Create: `backend/dto/session.py`
- Create: `backend/repositories/users.py`
- Create: `backend/repositories/sessions.py`
- Create: `backend/repositories/messages.py`
- Create: `backend/services/auth_service.py`
- Create: `backend/services/chat_service.py`
- Create: `backend/services/session_service.py`
- Create: `backend/services/gemini_service.py`
- Create: `backend/services/qdrant_service.py`
- Modify: `backend/api/routes/auth.py`
- Modify: `backend/api/routes/chat.py`
- Modify: `backend/api/routes/sessions.py`
- Modify: `backend/api/routes/__init__.py`
- Modify: `backend/main.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/routes/test_auth.py`
- Modify: `backend/tests/routes/test_sessions.py`
- Modify: `backend/tests/routes/test_chat.py`
- Modify: `backend/tests/services/test_gemini_service.py`
- Delete after cutover: `backend/config.py`, `backend/auth.py`, `backend/db.py`, `backend/models.py`, `backend/api/models/schemas.py`, `backend/api/services/gemini_service.py`, `backend/api/services/qdrant_service.py`

### Task 1: Create foundational layers and move shared infrastructure

**Files:**
- Create: `backend/core/config.py`
- Create: `backend/core/security.py`
- Create: `backend/db/base.py`
- Create: `backend/db/session.py`
- Create: `backend/db/init_db.py`
- Create: `backend/api/dependencies/database.py`
- Create: `backend/api/dependencies/auth.py`
- Test: `backend/tests/routes/test_auth.py`

- [ ] **Step 1: Write a failing import migration test**

Append to `backend/tests/routes/test_auth.py`
```python
from api.dependencies.auth import get_current_user


def test_new_auth_dependency_module_imports() -> None:
    assert callable(get_current_user)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_auth.py::test_new_auth_dependency_module_imports -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.dependencies'`

- [ ] **Step 3: Create new foundational modules**

`backend/core/config.py`
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

`backend/core/security.py`
```python
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.hash import sha256_crypt
from core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY


def hash_password(password: str) -> str:
    return sha256_crypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return sha256_crypt.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
```

`backend/db/base.py`
```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

`backend/db/session.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from core.config import NEON_DATABASE_URL

_engine_args = {"future": True, "poolclass": StaticPool}
if not NEON_DATABASE_URL:
    _engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(NEON_DATABASE_URL or "sqlite+pysqlite:///:memory:", **_engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```

`backend/db/init_db.py`
```python
from db.base import Base
from db.session import engine


def init_db() -> None:
    import entities.chat_message  # noqa: F401
    import entities.chat_session  # noqa: F401
    import entities.user  # noqa: F401

    Base.metadata.create_all(bind=engine)
```

`backend/api/dependencies/database.py`
```python
from collections.abc import Generator
from db.session import SessionLocal


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/api/dependencies/auth.py`
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from api.dependencies.database import get_db
from core.config import JWT_ALGORITHM, JWT_SECRET_KEY
from entities.user import User

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise unauthorized from exc

    user_id = payload.get("sub")
    if not user_id:
        raise unauthorized

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise unauthorized
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/routes/test_auth.py::test_new_auth_dependency_module_imports -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/config.py backend/core/security.py backend/db/base.py backend/db/session.py backend/db/init_db.py backend/api/dependencies/database.py backend/api/dependencies/auth.py backend/tests/routes/test_auth.py
git commit -m "refactor: add layered backend foundations"
```

### Task 2: Split entities and DTOs

**Files:**
- Create: `backend/entities/user.py`
- Create: `backend/entities/chat_session.py`
- Create: `backend/entities/chat_message.py`
- Create: `backend/dto/auth.py`
- Create: `backend/dto/chat.py`
- Create: `backend/dto/session.py`
- Modify: `backend/tests/routes/test_auth.py`
- Modify: `backend/tests/routes/test_chat.py`
- Modify: `backend/tests/routes/test_sessions.py`
- Modify: `backend/tests/services/test_gemini_service.py`

- [ ] **Step 1: Add failing entity/DTO import tests**

Append to `backend/tests/routes/test_sessions.py`
```python
from dto.session import SessionResponse
from entities.chat_session import ChatSession


def test_new_session_modules_import() -> None:
    assert SessionResponse is not None
    assert ChatSession is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_sessions.py::test_new_session_modules_import -v`
Expected: FAIL with `ModuleNotFoundError` for `dto` or `entities`

- [ ] **Step 3: Create entity files**

`backend/entities/user.py`
```python
from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

`backend/entities/chat_session.py`
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

`backend/entities/chat_message.py`
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 4: Create DTO files**

`backend/dto/auth.py`
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
```

`backend/dto/chat.py`
```python
from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] | None = None
```

`backend/dto/session.py`
```python
from pydantic import BaseModel


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

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/routes/test_sessions.py::test_new_session_modules_import -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/entities/user.py backend/entities/chat_session.py backend/entities/chat_message.py backend/dto/auth.py backend/dto/chat.py backend/dto/session.py backend/tests/routes/test_sessions.py
git commit -m "refactor: split entities and dto modules"
```

### Task 3: Add repositories and move DB queries out of routes

**Files:**
- Create: `backend/repositories/users.py`
- Create: `backend/repositories/sessions.py`
- Create: `backend/repositories/messages.py`
- Modify: `backend/api/routes/auth.py`
- Modify: `backend/api/routes/sessions.py`
- Modify: `backend/api/routes/chat.py`
- Test: `backend/tests/routes/test_auth.py`
- Test: `backend/tests/routes/test_sessions.py`
- Test: `backend/tests/routes/test_chat.py`

- [ ] **Step 1: Add failing repository import test**

Append to `backend/tests/routes/test_chat.py`
```python
from repositories.messages import create_message


def test_message_repository_imports() -> None:
    assert callable(create_message)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_chat.py::test_message_repository_imports -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'repositories'`

- [ ] **Step 3: Create repository modules**

`backend/repositories/users.py`
```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from entities.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

`backend/repositories/sessions.py`
```python
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from entities.chat_session import ChatSession


def create_session(db: Session, session: ChatSession) -> ChatSession:
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions_for_user(db: Session, user_id: str) -> list[ChatSession]:
    return db.execute(
        select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
    ).scalars().all()


def get_session_for_user(db: Session, session_id: str, user_id: str) -> ChatSession | None:
    return db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    ).scalar_one_or_none()


def delete_session_for_user(db: Session, session_id: str) -> None:
    db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    db.commit()
```

`backend/repositories/messages.py`
```python
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from entities.chat_message import ChatMessage


def create_message(db: Session, message: ChatMessage) -> ChatMessage:
    db.add(message)
    db.commit()
    return message


def list_messages_for_session(db: Session, session_id: str) -> list[ChatMessage]:
    return db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    ).scalars().all()


def delete_messages_for_session(db: Session, session_id: str) -> None:
    db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    db.commit()
```

- [ ] **Step 4: Update routes to use repositories instead of inline queries**

Implementation requirements:
- `auth.py` stops calling `select(User)` directly
- `sessions.py` stops calling `select(ChatSession)` and `delete(...)` directly
- `chat.py` stops using inline `get_session_for_user` and `save_chat_message` functions once repository functions exist

- [ ] **Step 5: Run focused route tests**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py tests/routes/test_chat.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/repositories/users.py backend/repositories/sessions.py backend/repositories/messages.py backend/api/routes/auth.py backend/api/routes/sessions.py backend/api/routes/chat.py backend/tests/routes/test_chat.py
git commit -m "refactor: move persistence into repositories"
```

### Task 4: Add services and thin route handlers

**Files:**
- Create: `backend/services/auth_service.py`
- Create: `backend/services/session_service.py`
- Create: `backend/services/chat_service.py`
- Create: `backend/services/gemini_service.py`
- Create: `backend/services/qdrant_service.py`
- Modify: `backend/api/routes/auth.py`
- Modify: `backend/api/routes/sessions.py`
- Modify: `backend/api/routes/chat.py`
- Modify: `backend/tests/services/test_gemini_service.py`

- [ ] **Step 1: Add failing service import test**

Append to `backend/tests/services/test_gemini_service.py`
```python
from services.gemini_service import build_prompt


def test_new_gemini_service_imports() -> None:
    prompt = build_prompt("Hỏi", ["Ngữ cảnh"])
    assert "Ngữ cảnh" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/test_gemini_service.py::test_new_gemini_service_imports -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services'`

- [ ] **Step 3: Create service modules**

`backend/services/gemini_service.py`
```python
from google import genai
from core.config import GEMINI_API_KEY, GEMINI_MODEL


def build_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks)
    return (
        "Bạn là trợ lý pháp luật Việt Nam. "
        "Chỉ dựa trên ngữ cảnh được cung cấp. "
        "Nếu ngữ cảnh không đủ, nói rõ là chưa đủ thông tin.\n\n"
        f"Ngữ cảnh:\n{context}\n\n"
        f"Câu hỏi: {question}"
    )


def generate_answer(question: str, contexts: list[dict[str, str]]) -> str:
    context_chunks = [item["content"] for item in contexts]
    prompt = build_prompt(question=question, context_chunks=context_chunks)
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text or "Không có câu trả lời phù hợp."
```

`backend/services/qdrant_service.py`
```python
from qdrant_client import QdrantClient
from core.config import QDRANT_API_KEY, QDRANT_URL


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def search_legal_context(message: str) -> list[dict[str, str]]:
    _ = message
    return []
```

Implementation requirements for service orchestrators:
- `auth_service.py`: register/login using repositories + core security helpers
- `session_service.py`: create/list/get/rename/delete session and list messages
- `chat_service.py`: validate ownership, persist user message, call qdrant/gemini services, persist assistant message, return `reply` and `sources`

- [ ] **Step 4: Update routes to delegate to services only**

Implementation requirements:
- `auth.py` route functions should call auth service helpers and do no direct DB work
- `sessions.py` route functions should call session service helpers and do no direct DB work
- `chat.py` route function should call one `chat_service.send_chat_message(...)`-style helper and stop orchestrating persistence inline

- [ ] **Step 5: Run focused tests**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py tests/routes/test_chat.py tests/services/test_gemini_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/auth_service.py backend/services/session_service.py backend/services/chat_service.py backend/services/gemini_service.py backend/services/qdrant_service.py backend/api/routes/auth.py backend/api/routes/sessions.py backend/api/routes/chat.py backend/tests/services/test_gemini_service.py
git commit -m "refactor: move business logic into services"
```

### Task 5: Cut over imports, app wiring, and remove obsolete modules

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/api/routes/__init__.py`
- Delete: `backend/config.py`
- Delete: `backend/auth.py`
- Delete: `backend/db.py`
- Delete: `backend/models.py`
- Delete: `backend/api/models/schemas.py`
- Delete: `backend/api/services/gemini_service.py`
- Delete: `backend/api/services/qdrant_service.py`

- [ ] **Step 1: Add failing obsolete-module check**

Append to `backend/tests/routes/test_auth.py`
```python
import importlib.util


def test_legacy_auth_module_removed() -> None:
    assert importlib.util.find_spec("auth") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_auth.py::test_legacy_auth_module_removed -v`
Expected: FAIL because legacy `auth.py` still exists

- [ ] **Step 3: Update remaining imports and delete obsolete files**

Implementation requirements:
- `main.py` and route modules import from new layered modules only
- tests and fixtures import `init_db` from `db.init_db`
- no remaining imports from `config`, `auth`, `db`, `models`, or `api.models.schemas`
- after import cutover, delete obsolete modules listed above

- [ ] **Step 4: Run full backend test suite**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py tests/routes/test_chat.py tests/services/test_gemini_service.py -v`
Expected: PASS

- [ ] **Step 5: Run grep verification for legacy imports**

Run: `cd backend && grep -R "from config\|from auth\|from db import\|from models\|api.models.schemas\|api.services.gemini_service\|api.services.qdrant_service" .`
Expected: no output from source files

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/conftest.py backend/api/routes/__init__.py backend/core backend/db backend/entities backend/dto backend/repositories backend/services backend/api/dependencies
git rm backend/config.py backend/auth.py backend/db.py backend/models.py backend/api/models/schemas.py backend/api/services/gemini_service.py backend/api/services/qdrant_service.py
git commit -m "refactor: adopt layered backend structure"
```

### Task 6: Final verification and docs note

**Files:**
- Modify: `docs/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing docs verification checklist**

```txt
1. README mentions layered backend refactor only if needed without changing product claims
2. docs/README.md still documents current APIs correctly after refactor
3. No docs still reference deleted backend module paths if any were mentioned
```

- [ ] **Step 2: Verify current docs/checks**

Run: `grep -R "backend/config.py\|backend/models.py\|api/models/schemas.py\|api/services/gemini_service.py" README.md docs/README.md`
Expected: no output, or identify any stale references to remove

- [ ] **Step 3: Update docs only if stale module-path references exist**

If stale references are found, remove or replace them with neutral wording. Keep product/API documentation stable; do not add architecture essays.

- [ ] **Step 4: Run final backend verification**

Run: `cd backend && pytest tests/routes/test_auth.py tests/routes/test_sessions.py tests/routes/test_chat.py tests/services/test_gemini_service.py -v`
Expected: PASS

Run: `cd backend && grep -R "from config\|from auth\|from db import\|from models\|api.models.schemas\|api.services.gemini_service\|api.services.qdrant_service" .`
Expected: no output from source files

- [ ] **Step 5: Commit**

```bash
git add README.md docs/README.md
git commit -m "chore: finalize layered backend refactor"
```

## Self-review

- Spec coverage: all target layers are created, mixed-responsibility files are split, route/business/data concerns are separated, old modules are removed after cutover, and verified endpoint behavior remains stable through tests.
- Placeholder scan: no TODO/TBD placeholders remain; each task specifies exact files, tests, commands, and migration actions.
- Type consistency: DTO names remain `RegisterRequest`, `LoginRequest`, `AuthResponse`, `ChatRequest`, `ChatResponse`, `SessionCreateRequest`, `SessionUpdateRequest`, `SessionResponse`, and `MessageResponse` throughout the plan.
