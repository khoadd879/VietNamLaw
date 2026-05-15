# Chatbot-only Gemini refactor design

## Goal
Convert app into chatbot-only experience at `/`, remove landing page, keep Qdrant-backed RAG, and switch answer generation to Gemini.

## Scope
- Replace landing page in `frontend/app/page.tsx` with chat UI as root experience.
- Keep frontend-to-backend chat request flow centered on existing `sendMessage` helper.
- Keep Qdrant retrieval in backend.
- Replace current placeholder/OpenAI-oriented LLM setup with Gemini-backed answer generation.
- Keep response shape as `reply` plus optional `sources`.
- Update docs and environment variable references from OpenAI to Gemini.

## Architecture
### Frontend
`frontend/app/page.tsx` becomes chat screen instead of marketing site. It should render:
- message list
- input box
- submit action
- loading state while waiting for backend
- simple error state if request fails
- optional source list per assistant reply if backend returns sources

No landing page sections remain. Root route becomes direct chat entrypoint.

### Backend
`POST /chat` remains primary API contract. Route handler should:
1. accept user message
2. retrieve relevant legal context from Qdrant
3. build Gemini prompt from user question plus retrieved context
4. call Gemini API
5. return generated reply and any source metadata exposed by retrieval layer

This keeps current RAG shape while changing only answer generation provider.

## Components and responsibilities
- `frontend/app/page.tsx`: chat-only page and local UI state
- `frontend/lib/api.ts`: browser API call to backend chat endpoint
- `backend/api/routes/chat.py`: request handling and response assembly
- backend Gemini service module: Gemini API call and prompt assembly
- `backend/api/services/qdrant_service.py`: retrieval access
- `backend/api/models/schemas.py`: request and response contracts

## Data flow
1. User opens `/`.
2. User submits legal question.
3. Frontend posts `{ message }` to backend.
4. Backend queries Qdrant for relevant context.
5. Backend sends question plus context to Gemini.
6. Backend returns `reply` and optional `sources`.
7. Frontend appends assistant message to chat transcript.

## Error handling
- Frontend shows simple failure message when request fails or backend returns non-OK status.
- Backend should fail request with clear API error if Gemini config is missing or Gemini call fails.
- Empty user message should not be submitted from frontend.

## Testing and verification
- Run frontend and backend locally.
- Open `/` and verify landing page is gone.
- Send at least one sample legal question.
- Confirm assistant reply renders in chat.
- Confirm loading and failure states behave sensibly.
- Confirm docs mention Gemini instead of OpenAI.

## Out of scope
- Multi-provider abstraction layer
- Auth/session/history persistence
- Streaming responses
- Advanced prompt management
