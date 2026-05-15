# Neon auth and chat history design

## Goal
Add required authentication and persistent chat history to the Vietnam law chatbot using Neon Postgres, so only registered users can use the product and all chat activity is stored by both `user_id` and `session_id`.

## Scope
- Add email/password registration and login.
- Require authentication before using chat APIs.
- Add Neon Postgres connection and backend persistence layer.
- Store chat sessions and chat messages in Neon.
- Expose full session history APIs: create, list, get, rename, delete, and read messages.
- Update chat send flow so each request is tied to an authenticated user and a valid session.

## Architecture
### Authentication
The backend adds an auth module with password-based registration and JWT bearer login.

Required endpoints:
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Passwords are never stored directly. The backend stores only password hashes. Every authenticated request uses a bearer token that resolves to one user record.

### Persistence
Neon becomes the system of record for users and chat history.

Proposed tables:
- `users`
  - `id` UUID primary key
  - `email` unique
  - `password_hash`
  - `created_at`
- `chat_sessions`
  - `id` UUID primary key
  - `user_id` foreign key to `users.id`
  - `title`
  - `created_at`
  - `updated_at`
- `chat_messages`
  - `id` UUID primary key
  - `session_id` foreign key to `chat_sessions.id`
  - `user_id` foreign key to `users.id`
  - `role` (`user` or `assistant`)
  - `content`
  - `sources_json` nullable JSON payload
  - `created_at`

Each message stores both `session_id` and `user_id`. This gives direct ownership checks and simpler auditing without depending only on joins through sessions.

### Chat flow
`POST /chat` stays the main generation endpoint, but becomes authenticated and session-aware.

Expected request shape:
- `message`
- `session_id`

Expected flow:
1. authenticate bearer token
2. verify `session_id` belongs to current user
3. save user message to Neon
4. retrieve legal context from Qdrant
5. generate assistant reply with Gemini
6. save assistant reply and source metadata to Neon
7. return `reply` and `sources`

The client should create a chat session explicitly before sending the first message. The backend should reject `POST /chat` when `session_id` is missing or does not belong to the authenticated user.

## API surface
### Auth
- `POST /auth/register`
  - input: `email`, `password`
  - output: authenticated user summary plus token, or user summary and separate login requirement if preferred during implementation
- `POST /auth/login`
  - input: `email`, `password`
  - output: JWT access token and user summary
- `GET /auth/me`
  - output: current authenticated user

### Chat sessions
- `POST /chat/sessions`
  - create new session for current user
  - optional initial title, else backend sets a default like `Cuộc trò chuyện mới`
- `GET /chat/sessions`
  - list current user sessions ordered by `updated_at` descending
- `GET /chat/sessions/{session_id}`
  - return session metadata for owner
- `PATCH /chat/sessions/{session_id}`
  - rename session title
- `DELETE /chat/sessions/{session_id}`
  - delete session and its messages for owner
- `GET /chat/sessions/{session_id}/messages`
  - return ordered messages for owner

### Chat send
- `POST /chat`
  - authenticated
  - requires `session_id`
  - stores user and assistant messages in Neon
  - returns existing public response shape: `reply`, optional `sources`

## Components and responsibilities
- `backend/config.py`: Neon connection string, JWT secret, token settings, password hashing config
- backend database module: connection/session factory for Neon Postgres
- backend auth service module: register, authenticate, hash/verify passwords, create/parse JWT
- backend repository or service modules: CRUD for users, chat sessions, chat messages
- `backend/api/routes/chat.py`: enforce auth, verify session ownership, persist messages around existing RAG flow
- new auth route module: register/login/me endpoints
- new session route module: session CRUD and message listing
- `backend/api/models/schemas.py`: request/response models for auth, sessions, and messages

## Security and ownership rules
- Unauthenticated users cannot access chat or history endpoints.
- Only the owner may read, rename, or delete a session.
- Only the owner may read messages in that session.
- Passwords are hashed before persistence.
- JWT validation failure returns unauthorized.
- Session ownership failure returns not found or forbidden; implementation should choose one consistent policy and keep it explicit.

## Error handling
- Duplicate registration email returns a clear conflict error.
- Invalid login credentials return unauthorized.
- Missing or invalid bearer token returns unauthorized.
- Unknown session ID or foreign session ID returns an authorization-safe error.
- Neon connection/config issues return server errors with no secret leakage.
- If Gemini generation fails after the user message is stored, the backend should return an error response and avoid storing a fake assistant reply.

## Testing and verification
- Registration success and duplicate email rejection
- Login success and invalid password rejection
- Auth guard on chat and session endpoints
- Session create/list/get/rename/delete ownership checks
- Message listing only for owner
- `POST /chat` stores both user and assistant messages under same session and user
- Existing Gemini/Qdrant wiring still returns `reply` and `sources`
- Frontend follow-up work should confirm users cannot access chat UI until authenticated

## Out of scope
- Google OAuth
- Password reset or email verification
- Multi-device session management UI
- Token refresh flow
- Sharing chat sessions across users
- Full frontend auth implementation in this spec unless needed later as a separate plan
