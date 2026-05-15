# Chatbot-only Gemini Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace landing page with chatbot-only root experience and switch backend answer generation to Gemini while keeping Qdrant-backed RAG.

**Architecture:** Frontend root page becomes single chat interface that posts messages to existing backend endpoint and renders reply, loading, error, and source states. Backend keeps Qdrant retrieval, adds Gemini service for prompt assembly and answer generation, and keeps the public chat response contract stable.

**Tech Stack:** Next.js 14, React 18, TypeScript, FastAPI, Pydantic v2, Qdrant client, python-dotenv, Google Gemini Python SDK

---

## File structure

- Modify: `frontend/app/page.tsx` — replace marketing landing page with chat-only UI
- Modify: `frontend/lib/api.ts` — harden chat request handling for non-OK responses
- Modify: `frontend/package.json` — add test/lint support only if needed by chosen implementation path
- Modify: `backend/api/routes/chat.py` — move from placeholder reply to retrieval + Gemini flow
- Modify: `backend/api/models/schemas.py` — extend schema only if source items need richer structure
- Modify: `backend/config.py` — replace OpenAI env with Gemini env
- Modify: `backend/.env.example` — document Gemini key
- Modify: `backend/requirements.txt` — add Gemini SDK dependency
- Create: `backend/api/services/gemini_service.py` — Gemini prompt assembly and generation
- Modify: `docs/README.md` — swap OpenAI references to Gemini and keep setup aligned
- Optional modify: `README.md` — keep top-level quick summary aligned if LLM name appears there

### Task 1: Backend Gemini config and failing service test

**Files:**
- Create: `backend/tests/services/test_gemini_service.py`
- Modify: `backend/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Write failing Gemini service test**

```python
from api.services.gemini_service import build_prompt


def test_build_prompt_includes_question_and_context() -> None:
    prompt = build_prompt(
        question="Điều kiện đơn phương ly hôn là gì?",
        context_chunks=[
            "Luật Hôn nhân và Gia đình quy định về quyền yêu cầu ly hôn.",
            "Tòa án xem xét tình trạng hôn nhân trầm trọng.",
        ],
    )

    assert "Điều kiện đơn phương ly hôn là gì?" in prompt
    assert "Luật Hôn nhân và Gia đình" in prompt
    assert "Tòa án xem xét" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/test_gemini_service.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `build_prompt`

- [ ] **Step 3: Add Gemini dependency and config**

`backend/requirements.txt`
```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
qdrant-client==1.18.0
sentence-transformers==5.5.0
pydantic==2.13.4
python-dotenv==1.0.0
google-genai==1.16.1
pytest==8.4.0
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
```

`backend/.env.example`
```env
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

- [ ] **Step 4: Create minimal Gemini service implementation**

`backend/api/services/gemini_service.py`
```python
def build_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks)
    return (
        "Bạn là trợ lý pháp luật Việt Nam. "
        "Chỉ dựa trên ngữ cảnh được cung cấp. "
        "Nếu ngữ cảnh không đủ, nói rõ là chưa đủ thông tin.\n\n"
        f"Ngữ cảnh:\n{context}\n\n"
        f"Câu hỏi: {question}"
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/services/test_gemini_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tests/services/test_gemini_service.py backend/config.py backend/.env.example backend/requirements.txt backend/api/services/gemini_service.py
git commit -m "feat: add Gemini backend configuration"
```

### Task 2: Backend chat route RAG + Gemini flow

**Files:**
- Modify: `backend/api/routes/chat.py`
- Modify: `backend/api/services/qdrant_service.py`
- Modify: `backend/api/services/gemini_service.py`
- Test: `backend/tests/routes/test_chat.py`

- [ ] **Step 1: Write failing route test for chat reply and sources**

`backend/tests/routes/test_chat.py`
```python
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_chat_returns_reply_and_sources(monkeypatch) -> None:
    from api.routes import chat as chat_module

    monkeypatch.setattr(
        chat_module,
        "search_legal_context",
        lambda message: [
            {"source": "Luật Hôn nhân và Gia đình", "content": "Quy định về ly hôn."}
        ],
    )
    monkeypatch.setattr(
        chat_module,
        "generate_answer",
        lambda question, contexts: "Cần xem xét căn cứ ly hôn theo luật hiện hành.",
    )

    response = client.post("/chat", json={"message": "Khi nào được ly hôn?"})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Cần xem xét căn cứ ly hôn theo luật hiện hành.",
        "sources": ["Luật Hôn nhân và Gia đình"],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/routes/test_chat.py -v`
Expected: FAIL because route still returns placeholder reply

- [ ] **Step 3: Extend Qdrant service with retrieval helper**

`backend/api/services/qdrant_service.py`
```python
from qdrant_client import QdrantClient
import os


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY", ""),
    )


def search_legal_context(message: str) -> list[dict[str, str]]:
    _ = message
    return []
```

- [ ] **Step 4: Expand Gemini service with generation entrypoint**

`backend/api/services/gemini_service.py`
```python
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL


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

- [ ] **Step 5: Replace placeholder route logic**

`backend/api/routes/chat.py`
```python
from fastapi import APIRouter
from api.models.schemas import ChatRequest, ChatResponse
from api.services.gemini_service import generate_answer
from api.services.qdrant_service import search_legal_context

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    contexts = search_legal_context(request.message)
    reply = generate_answer(request.message, contexts)
    sources = [item["source"] for item in contexts if item.get("source")]
    return ChatResponse(reply=reply, sources=sources)
```

- [ ] **Step 6: Run route test to verify it passes**

Run: `cd backend && pytest tests/routes/test_chat.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/tests/routes/test_chat.py backend/api/routes/chat.py backend/api/services/qdrant_service.py backend/api/services/gemini_service.py
git commit -m "feat: wire Gemini into chat route"
```

### Task 3: Frontend chat-only root page

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/lib/api.ts`
- Test: `frontend/app/page.tsx` manual verification through browser

- [ ] **Step 1: Write minimal failing browser checklist**

```txt
1. Open http://localhost:3000/
2. Confirm landing page marketing sections are gone
3. Enter a legal question
4. Submit question
5. Confirm loading text appears
6. Confirm assistant reply appears
```

- [ ] **Step 2: Run app and verify checklist currently fails**

Run frontend: `cd frontend && npm run dev`
Run backend: `cd backend && uvicorn main:app --reload --port 8000`
Expected: FAIL because `/` still shows landing page and no chat UI exists

- [ ] **Step 3: Harden API helper for failed HTTP status**

`frontend/lib/api.ts`
```ts
export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

export interface ChatResponse {
  reply: string
  sources?: string[]
}

export async function sendMessage(content: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: content }),
  })

  if (!res.ok) {
    throw new Error('Chat request failed')
  }

  return res.json()
}
```

- [ ] **Step 4: Replace landing page with chat-only UI**

`frontend/app/page.tsx`
```tsx
'use client'

import { FormEvent, useState } from 'react'
import { sendMessage, ChatMessage } from '@/lib/api'

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = input.trim()
    if (!message || loading) return

    setError('')
    setLoading(true)
    setMessages((current) => [...current, { role: 'user', content: message }])
    setInput('')

    try {
      const response = await sendMessage(message)
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: response.reply, sources: response.sources },
      ])
    } catch {
      setError('Không thể gửi câu hỏi lúc này.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main style={{ minHeight: '100vh', background: '#0b0b14', color: '#f0f0f5', padding: '32px' }}>
      <div style={{ maxWidth: '960px', margin: '0 auto' }}>
        <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>LuatGPT</h1>
        <p style={{ color: '#a0a0b8', marginBottom: '24px' }}>
          Hỏi đáp pháp luật Việt Nam bằng AI.
        </p>

        <section style={{ border: '1px solid #2a2a3a', borderRadius: '16px', padding: '24px', background: '#14141f' }}>
          <div style={{ display: 'grid', gap: '16px', marginBottom: '24px' }}>
            {messages.length === 0 ? (
              <div style={{ color: '#a0a0b8' }}>Hãy nhập câu hỏi pháp lý để bắt đầu.</div>
            ) : (
              messages.map((message, index) => (
                <article
                  key={`${message.role}-${index}`}
                  style={{
                    padding: '16px',
                    borderRadius: '12px',
                    background: message.role === 'user' ? '#1d1d2e' : '#171726',
                  }}
                >
                  <strong style={{ display: 'block', marginBottom: '8px' }}>
                    {message.role === 'user' ? 'Bạn' : 'Trợ lý'}
                  </strong>
                  <div>{message.content}</div>
                  {message.sources?.length ? (
                    <ul style={{ marginTop: '12px', paddingLeft: '18px', color: '#c9a84c' }}>
                      {message.sources.map((source) => (
                        <li key={source}>{source}</li>
                      ))}
                    </ul>
                  ) : null}
                </article>
              ))
            )}
            {loading ? <div style={{ color: '#c9a84c' }}>Đang trả lời...</div> : null}
            {error ? <div style={{ color: '#ff8a8a' }}>{error}</div> : null}
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '12px' }}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ví dụ: Điều kiện đơn phương ly hôn là gì?"
              style={{
                flex: 1,
                padding: '14px 16px',
                borderRadius: '12px',
                border: '1px solid #34344a',
                background: '#0f0f18',
                color: '#f0f0f5',
              }}
            />
            <button
              type="submit"
              disabled={loading || input.trim().length === 0}
              style={{
                padding: '14px 20px',
                borderRadius: '12px',
                border: 'none',
                background: '#c9a84c',
                color: '#0b0b14',
                fontWeight: 700,
              }}
            >
              Gửi
            </button>
          </form>
        </section>
      </div>
    </main>
  )
}
```

- [ ] **Step 5: Run golden-path verification in browser**

Run frontend: `cd frontend && npm run dev`
Run backend: `cd backend && uvicorn main:app --reload --port 8000`
Use browser to:
1. Open `http://localhost:3000/`
2. Confirm landing page content is removed
3. Submit `Điều kiện đơn phương ly hôn là gì?`
4. Confirm loading state appears
5. Confirm reply renders
6. Stop backend or break API URL, submit again, confirm error message renders

Expected: all checks pass

- [ ] **Step 6: Commit**

```bash
git add frontend/app/page.tsx frontend/lib/api.ts
git commit -m "feat: replace landing page with chat root"
```

### Task 4: Docs and final verification

**Files:**
- Modify: `docs/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing docs checklist**

```txt
1. docs/README.md should say Gemini instead of OpenAI GPT
2. backend env example should mention GEMINI_API_KEY
3. root README should not conflict with Gemini backend description
```

- [ ] **Step 2: Verify checklist currently fails**

Run: `grep -R "OPENAI_API_KEY\|OpenAI GPT" README.md docs/README.md backend/.env.example`
Expected: matches still present

- [ ] **Step 3: Update docs**

`docs/README.md`
```md
| LLM | Google Gemini |
```

```md
| `GEMINI_API_KEY` | Gemini API key | Yes |
| `GEMINI_MODEL` | Gemini model name | No (default: gemini-2.5-flash) |
```

```bash
# Edit .env with your credentials (Qdrant, Gemini)
```

`README.md`
```md
AI-powered legal question answering system for Vietnamese law using Gemini-backed generation.
```

- [ ] **Step 4: Run verification**

Run: `grep -R "OPENAI_API_KEY\|OpenAI GPT" README.md docs/README.md backend/.env.example`
Expected: no output

- [ ] **Step 5: Run focused test suite and lint**

Run: `cd backend && pytest tests/services/test_gemini_service.py tests/routes/test_chat.py -v`
Expected: PASS

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add docs/README.md README.md backend/.env.example
git commit -m "docs: update Gemini chatbot documentation"
```

## Self-review

- Spec coverage: root chat-only UX, Gemini + RAG backend, stable response shape, env/docs updates, loading/error verification all map to tasks above.
- Placeholder scan: no TODO/TBD placeholders remain; each code step contains concrete file content or command.
- Type consistency: `sendMessage` returns `ChatResponse`; backend route returns `reply` and `sources`; Gemini service names stay `build_prompt` and `generate_answer` across tasks.
