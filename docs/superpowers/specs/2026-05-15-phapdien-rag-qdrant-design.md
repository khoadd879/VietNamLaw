# Spec: RAG Pipeline for phapdien-moj-gov-vn Dataset

## Overview

Build a RAG pipeline that loads Vietnamese legal articles from HuggingFace, embeds them via Gemini, stores in Qdrant Cloud, and integrates with the existing chatbot.

## Dataset

- Source: `tmquan/phapdien-moj-gov-vn` (HuggingFace)
- Subset: `articles` (64,500 rows)
- Fields used: `content_text`, `article_title`, `article_anchor`, `topic_title`, `topic_id`, `demuc_title`, `demuc_id`, `source_url`

## Architecture

```
HuggingFace Dataset
       ↓
  Load & Parse
       ↓
  Chunk (per article = 1 document)
       ↓
  Gemini Embedding API (embedding-001)
       ↓
  Qdrant Cloud (collection: legal_articles)
       ↓
  Chatbot Query
       ↓
  Gemini Answer Generation
```

## Components

### 1. Ingestion Script: `scripts/ingest_phapdien.py`

Standalone script, run manually (not at startup).

**Flow:**
1. Load dataset from HuggingFace
2. For each article:
   - Extract `content_text` (source) + metadata
   - Skip if `content_text` is empty
3. Batch embed via Gemini `embedding-001` (batch size: 100, configurable)
4. Upsert batch to Qdrant Cloud collection
5. Write checkpoint after each batch

**Checkpoint:** `data/.ingest_checkpoint.json`
```json
{
  "last_processed_index": 12500,
  "last_processed_id": "...",
  "timestamp": "2026-05-15T10:30:00"
}
```
Resume: if checkpoint exists, skip to `last_processed_index + 1`.

### 2. Qdrant Collection Schema

Collection name: `legal_articles` (configurable via `QDRANT_COLLECTION_NAME`)

- Vector size: 768 (Gemini embedding-001 default)
- Distance: Cosine
- Payloads indexed: `topic_title`, `demuc_title`, `article_anchor`, `source_url`

**Point structure:**
```json
{
  "id": "<article_anchor>",
  "vector": [768 dims],
  "payload": {
    "content_text": "...",
    "article_title": "...",
    "article_anchor": "...",
    "topic_title": "...",
    "topic_id": "...",
    "demuc_title": "...",
    "demuc_id": "...",
    "source_url": "..."
  }
}
```

### 3. Updated `services/qdrant_service.py`

```python
def get_qdrant_client() -> QdrantClient
def ensure_collection_exists(client: QdrantClient)
def embed_texts(texts: list[str]) -> list[list[float]]
def ingest_articles(articles: list[dict], batch_size: int = 100)
def search_legal_context(
    message: str,
    filters: dict | None = None,
    top_k: int = 5
) -> list[dict[str, str]]
```

**`search_legal_context` behavior:**
- Embed message via Gemini
- ANN search in Qdrant with optional filter
- Filter: if `filters["topic_title"]` or `filters["demuc_title"]` provided, apply as `must` clause
- Return top_k results with `content_text`, `article_title`, `source_url`, `score`

### 4. Updated `services/chat_service.py`

`send_chat_message` calls `search_legal_context(message)` (no filter for now) → contexts → `generate_answer(message, contexts)`.

### 5. Configuration: `.env`

```env
QDRANT_URL=https://<your-cluster>.qdrant.tech
QDRANT_API_KEY=<your-api-key>
QDRANT_COLLECTION_NAME=legal_articles
GEMINI_EMBEDDING_MODEL=embedding-001
INGEST_BATCH_SIZE=100
```

## Environment Setup Steps

1. Create Qdrant Cloud account → create cluster → copy cluster URL
2. Create collection `legal_articles` with vector size 768
3. Get API key from Qdrant dashboard
4. Add to `.env`
5. Run `python scripts/ingest_phapdien.py`
6. Verify: query Qdrant via dashboard or script → should see 64,500 vectors

## Data Flow at Query Time

1. User sends message to chatbot
2. `send_chat_message` → `search_legal_context(message)`
3. `qdrant_service.search_legal_context` embeds message → ANN search → returns top-5 articles
4. Articles as context → `generate_answer(message, contexts)`
5. Reply + sources returned to user

## Files to Create/Modify

| File | Action |
|------|--------|
| `scripts/ingest_phapdien.py` | Create |
| `backend/services/qdrant_service.py` | Modify — add embed + search functions |
| `backend/core/config.py` | Add `QDRANT_COLLECTION_NAME`, `GEMINI_EMBEDDING_MODEL`, `INGEST_BATCH_SIZE` |
| `backend/services/chat_service.py` | No change needed (already calls search_legal_context) |
| `backend/.env` | Add Qdrant Cloud config |

## No Changes to Frontend

Frontend chatbot already calls `/chat` API. Backend changes are transparent to user.

## Testing

- Run ingestion script → verify point count in Qdrant dashboard = 64,500
- Run manual search test via Python script or API call
- Chatbot should return sourced answers (sources = `source_url` from Qdrant)