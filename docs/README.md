# Vietnam Legal Chatbot

RAG-powered chatbot for Vietnamese legal documents using FastAPI, Next.js, and Qdrant.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 14 (TypeScript) |
| Vector DB | Qdrant Cloud |
| Embeddings | sentence-transformers |
| LLM | Google Gemini |

## Project Structure

```
vietnam-law-chatbot/
├── backend/          # FastAPI API
├── frontend/         # Next.js app
├── docs/             # Documentation
└── data/             # Legal documents
```

## Quick Start

### 1. Backend Setup

```bash
cd backend
cp .env.example .env
# Edit .env with your credentials (Qdrant, Gemini)

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 3. Open Browser

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Environment Variables

### Backend (.env)

| Variable | Description | Required |
|----------|-------------|----------|
| `QDRANT_URL` | Qdrant Cloud cluster URL | Yes |
| `QDRANT_API_KEY` | Qdrant Cloud API key | Yes |
| `NEON_DATABASE_URL` | Neon Postgres connection string | Yes |
| `JWT_SECRET_KEY` | JWT signing secret | Yes |
| `JWT_ALGORITHM` | JWT signing algorithm | No (default: HS256) |
| `JWT_EXPIRE_MINUTES` | Access token expiry in minutes | No (default: 60) |
| `DATA_DIR` | Path to legal documents | No (default: ../data) |

### Frontend (.env.local)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | http://localhost:8000 |

## API Endpoints

- `POST /auth/register` - Register and receive access token
- `POST /auth/login` - Login and receive access token
- `GET /auth/me` - Get current authenticated user
- `POST /chat/sessions` - Create chat session
- `GET /chat/sessions` - List current user chat sessions
- `GET /chat/sessions/{session_id}` - Get session metadata
- `PATCH /chat/sessions/{session_id}` - Rename session
- `DELETE /chat/sessions/{session_id}` - Delete session and messages
- `GET /chat/sessions/{session_id}/messages` - List messages in a session