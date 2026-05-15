# Vietnamese Legal Chatbot

Authenticated legal chatbot with Neon-backed user accounts and session history.

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Next.js 14 (React + TypeScript)
- **Database**: Neon Postgres
- **Auth**: JWT (email/password)
- **Vector DB**: Qdrant
- **LLM**: Google Gemini

## Project Structure

```
VietNamLaw/
├── backend/      # FastAPI application
├── frontend/     # Next.js application
└── docs/         # Documentation
```

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
# Add NEON_DATABASE_URL, JWT_SECRET_KEY, GEMINI_API_KEY, QDRANT credentials
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Open

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Features

- Legal question answering
- Vietnamese text processing
- Vector similarity search
- RAG pipeline

