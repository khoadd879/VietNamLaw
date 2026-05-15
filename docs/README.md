# Vietnam Legal Chatbot

RAG-powered chatbot for Vietnamese legal documents using FastAPI, Next.js, and Qdrant.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 14 (TypeScript) |
| Vector DB | Qdrant Cloud |
| Embeddings | sentence-transformers |
| LLM | OpenAI GPT |

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
# Edit .env with your credentials (Qdrant, OpenAI)

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
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `DATA_DIR` | Path to legal documents | No (default: ../data) |

### Frontend (.env.local)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | http://localhost:8000 |

## API Endpoints

- `POST /api/chat` - Chat with legal documents
- `GET /api/health` - Health check
- `POST /api/index` - Re-index documents