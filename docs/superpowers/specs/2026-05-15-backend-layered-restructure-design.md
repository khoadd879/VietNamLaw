# Backend layered restructure design

## Goal
Restructure the backend into a cleaner layered architecture without changing product behavior, while also cleaning up files that currently mix routing, business logic, security logic, and data access.

## Scope
- Move backend code into explicit layers: `api`, `dependencies`, `core`, `db`, `entities`, `dto`, `repositories`, `services`.
- Split mixed-responsibility files into focused modules.
- Preserve existing API behavior for auth, chat, sessions, Gemini, and Qdrant integrations.
- Preserve current test behavior and keep the same endpoints and response contracts.
- Update imports, app wiring, and tests to match the new structure.

## Target structure
- `backend/api/routes/`
  - `auth.py`
  - `chat.py`
  - `sessions.py`
- `backend/api/dependencies/`
  - `auth.py`
  - `database.py`
- `backend/core/`
  - `config.py`
  - `security.py`
- `backend/db/`
  - `base.py`
  - `session.py`
  - `init_db.py`
- `backend/entities/`
  - `user.py`
  - `chat_session.py`
  - `chat_message.py`
- `backend/dto/`
  - `auth.py`
  - `chat.py`
  - `session.py`
- `backend/repositories/`
  - `users.py`
  - `sessions.py`
  - `messages.py`
- `backend/services/`
  - `auth_service.py`
  - `chat_service.py`
  - `session_service.py`
  - `gemini_service.py`
  - `qdrant_service.py`

## Architecture
### Route layer
Route modules should only do HTTP concerns:
- parse request DTOs
- call dependencies
- delegate to services
- return response DTOs or raise HTTP errors

Routes should stop containing DB queries, password hashing, JWT parsing, or chat persistence orchestration.

### Dependency layer
Shared FastAPI dependency functions live under `api/dependencies/`.

This includes:
- database session dependency
- authenticated current-user dependency

These dependencies may call lower-level core/db helpers, but route files should import them only from the dependency layer.

### Core layer
`core/` holds application-wide infrastructure logic that is not domain-specific:
- environment/config loading
- JWT encode/decode helpers
- password hash/verify helpers

This replaces the current mixed `config.py` and `auth.py` responsibilities.

### DB layer
`db/` owns SQLAlchemy base, engine/session construction, and initialization helpers. It should not own feature logic.

### Entity layer
`entities/` holds ORM models only. Each entity gets its own file so users, chat sessions, and chat messages stop sharing one large model file.

### DTO layer
`dto/` holds request/response schemas only. Split current mixed schema file into focused modules for auth, chat, and session history.

### Repository layer
`repositories/` owns raw persistence operations:
- find/create user
- find/create/update/delete session
- create/list messages

Repository functions should receive a DB session and return ORM objects or primitive values. They should not do HTTP-specific work.

### Service layer
`services/` owns business logic:
- registration/login flow
- session history orchestration
- authenticated chat flow
- Gemini generation
- Qdrant retrieval

This is where route-independent use cases should live. The chat service should coordinate session ownership validation, persistence, retrieval, generation, and response assembly.

## Cleanup rules
- If a file currently mixes concerns, split it rather than moving it intact.
- Do not change endpoint paths, request field names, or response shapes.
- Do not change persistence semantics unless needed to preserve behavior after refactor.
- Keep Gemini and Qdrant services as service-layer modules.
- Keep tests focused on behavior, but update imports/fixtures to the new structure.

## Migration mapping from current files
- `backend/config.py` → `backend/core/config.py`
- `backend/auth.py` → split into `backend/core/security.py` and `backend/api/dependencies/auth.py`
- `backend/db.py` → split into `backend/db/base.py`, `backend/db/session.py`, `backend/api/dependencies/database.py`, optional `backend/db/init_db.py`
- `backend/models.py` → split into `backend/entities/user.py`, `backend/entities/chat_session.py`, `backend/entities/chat_message.py`
- `backend/api/models/schemas.py` → split into `backend/dto/auth.py`, `backend/dto/chat.py`, `backend/dto/session.py`
- `backend/api/services/gemini_service.py` → `backend/services/gemini_service.py`
- `backend/api/services/qdrant_service.py` → `backend/services/qdrant_service.py`
- `backend/api/routes/auth.py` → stay as route file but delegate to services/repositories/dependencies
- `backend/api/routes/chat.py` → stay as route file but delegate to chat service
- `backend/api/routes/sessions.py` → stay as route file but delegate to session service

## Data flow after refactor
### Register
route → auth dependency/core validation as needed → auth service → user repository → token creation → response DTO

### Login
route → auth service → user repository lookup → password verification in core security → token creation → response DTO

### Session CRUD
route → current-user dependency → session service → session/message repositories → response DTO

### Chat
route → current-user dependency + db dependency → chat service → session repository ownership check → message repository save user message → qdrant service → gemini service → message repository save assistant message → response DTO

## Testing and verification
- Existing auth/session/chat/Gemini tests must still pass after refactor.
- Imports in tests and fixtures must point to the new module locations.
- Endpoint behavior must remain unchanged from the current verified implementation.
- A final verification pass should confirm no route still owns business logic or direct SQLAlchemy query assembly that belongs in repositories/services.

## Out of scope
- New features or endpoint changes
- Changing auth strategy
- Changing DB schema
- Changing frontend behavior
- Rewriting tests beyond what import and fixture updates require
