# RAG Ingestion Handoff — VietNamLaw

## Current State (2026-05-21)

**Dataset:** `th1nhng0/vietnamese-legal-documents`
**Configs used:** `metadata`, `content`, `relationships`
**Split:** `data`
**Granularity:** chunk-level records derived from cleaned `content_html`
**Qdrant Collection:** `legal_articles` — 1024 dims, cosine similarity
**Embedding Model:** Ollama `bge-m3` (local, 1024 dims)
**Checkpoint:** `data/.ingest_articles.json`
**Chunking strategy:** legal-aware (law docs split by Điều, decision-style fallback to paragraph)

---

## Chunk Metadata

Each vector in Qdrant carries the following fields for legal-aware retrieval:

```json
{
  "id": "<string>",
  "doc_id": "<string>",
  "title": "<string>",
  "chunk_level": "chapter | article | sub_article | sub_chapter | paragraph",
  "chunk_index": 0,
  "total_chunks": 1,
  "chapter_label": "<string | null>",
  "article_label": "<string | null>",
  "so_ky_hieu": "<string>",
  "loai_van_ban": "<string>",
  "co_quan_ban_hanh": "<string>",
  "tinh_trang_hieu_luc": "<string>",
  "linh_vuc": "<string>",
  "nganh": "<string>",
  "source_url": "<string>",
  "relationships": [
    {
      "other_doc_id": "<string>",
      "relationship": "<string>"
    }
  ]
}
```

| Chunk Level | Source | When Used |
|-------------|--------|-----------|
| `article` | Full `Điều` text | Standard law-style articles where content ≤ `LEGAL_CHUNK_MAX_CHARS` |
| `sub_article` | Paragraph sub-splits inside the same `Điều` | Long articles exceeding `LEGAL_CHUNK_MAX_CHARS` |
| `chapter` | Full `Chương` text | Law-style documents with chapters but no `Điều` structure, where content ≤ `LEGAL_CHUNK_MAX_CHARS` |
| `sub_chapter` | Paragraph sub-splits inside a `Chương` or full document | Long chapters without `Điều`, or decision-style documents (no stable Điều structure) |
| `paragraph` | `\n\n` separated blocks | Final fallback; documents with no identifiable chapter or article structure |

---

## Continue Ingestion

```bash
cd /home/khoa/Company/VietNamLaw
backend/.venv/bin/python scripts/ingest_phapdien.py
```

Script auto-resumes from `data/.ingest_articles.json`.

---

## Monitor Progress

```bash
backend/.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
i = c.get_collection(QDRANT_COLLECTION_NAME)
print(f'points: {i.points_count}, vector_size: {i.config.params.vectors.size}')
"

cat data/.ingest_articles.json
```

Progress should be interpreted against the latest checkpoint and smoke-test limits, not against the old fixed `64,464` article total. Point count can exceed processed document count because one document may produce multiple chunks.

---

## If Issues

| Issue | Solution |
|-------|----------|
| `ArrowInvalid: Failed casting from large_string to string` | Keep using the script's direct parquet path for `content` and `relationships`; this avoids the current `datasets` casting issue |
| Missing HTML content for a document | Expected for PDF-only rows; the script skips those records |
| `ReadTimeout` on Ollama | Increase `_EMBED_TIMEOUT_SECONDS` in `backend/services/qdrant_service.py` |
| Qdrant collection wrong dim | Delete and recreate collection |
| Chunking rules changed | See "Reset Checkpoint After Chunking Change" section below |

---

## Reset Checkpoint After Chunking Change

When chunking strategy, `LEGAL_CHUNK_MAX_CHARS`, or chunk metadata fields change, you **must** reset checkpoint to avoid inconsistent chunk IDs and vectors:

```bash
# 1. Remove stale checkpoint
rm data/.ingest_articles.json

# 2. Delete old Qdrant collection (if dimensions or metadata schema changed)
#    Use Qdrant dashboard or:
#    backend/.venv/bin/python -c "
#    from dotenv import load_dotenv; load_dotenv()
#    from services.qdrant_service import get_qdrant_client
#    from core.config import QDRANT_COLLECTION_NAME
#    c = get_qdrant_client()
#    c.delete_collection(QDRANT_COLLECTION_NAME)
#    print('Deleted', QDRANT_COLLECTION_NAME)
#    "

# 3. Re-create collection if needed (script handles this on first run)

# 4. Re-ingest from scratch
backend/.venv/bin/python scripts/ingest_phapdien.py --reset-checkpoint
```

**Why?** The checkpoint records the last-processed `doc_id`. Old vectors were embedded under the previous chunking rules and will not match re-retrieval queries that rely on new chunk boundaries.

---

## After Complete

```bash
backend/.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
i = c.get_collection(QDRANT_COLLECTION_NAME)
print(f'Final: {i.points_count} points, {i.config.params.vectors.size} dims')
"

bash run.sh
```
