# RAG Ingestion Handoff — VietNamLaw

Mục đích: tài liệu để bạn mở repo này trên máy khác và tiếp tục ingest legal corpus mới từ `th1nhng0/vietnamese-legal-documents` lên Qdrant Cloud mà không cần đọc lại lịch sử chat.

## 1. Stack hiện tại

- **Backend**: FastAPI trong `backend/`
- **Frontend**: Next.js trong `frontend/`
- **Vector DB**: Qdrant Cloud, collection `legal_articles`, 1024 chiều, cosine
- **Embedding**: Ollama `bge-m3`
- **Answer LLM**: Groq
- **Dataset**: HuggingFace `th1nhng0/vietnamese-legal-documents`
- **Configs dùng để ingest**: `metadata`, `content`, `relationships`
- **Split**: `data`
- **Granularity**: chunk-level records từ `content_html` đã làm sạch

## 2. Cách ingest hiện tại

Script `scripts/ingest_phapdien.py`:
- load `metadata` qua `datasets.load_dataset(...)`
- tải `content.parquet` và `relationships.parquet` trực tiếp từ Hugging Face Hub
- đọc parquet bằng `pyarrow` để tránh lỗi `datasets` + `large_string`
- join bằng `doc_id`
- clean HTML -> plain text
- split thành chunks theo `LEGAL_CHUNK_MAX_CHARS` với chiến lược **legal-aware** (xem bên dưới)
- upsert từng chunk vào Qdrant với metadata VBPL

## 2a. Legal-Aware Chunking Strategy

### Luật / Nghị định / Thông tư (Law-style documents — detected by ≥ N articles or at least 1 chapter)

Cấu trúc pháp lý ưu tiên: `Chương > Điều > Mục > Khoản > Điểm`

| Chunk Level | Tách theo | Chi tiết |
|-------------|-----------|----------|
| `article` | `Điều` | Mỗi Điều = 1 chunk nếu nội dung ≤ `LEGAL_CHUNK_MAX_CHARS` |
| `sub_article` | Paragraph sub-splits bên trong cùng `Điều` | Dùng khi một Điều vượt `LEGAL_CHUNK_MAX_CHARS`; vẫn giữ `article_label` và `chapter_label` |
| `chapter` | `Chương` | Cả Chương ≤ `LEGAL_CHUNK_MAX_CHARS` |
| `sub_chapter` | Paragraph sub-splits bên trong `Chương` | Dùng khi cả Chương vượt `LEGAL_CHUNK_MAX_CHARS` nhưng không có `Điều` |
| `paragraph` | `\n\n` (fallback cuối cùng) | Không có cấu trúc pháp lý rõ ràng |

**Quy tắc:**
- Luôn giữ `Điều <number>` làm ranh giới chunk chính khi có cấu trúc điều
- Điều dài: tách theo `Mục` trước, sau đó theo `Khoản` nếu vẫn còn dài
- Metadata bắt buộc: `chapter_label`, `article_label`, `chunk_level`

### Quyết định / Quyết phạm (Decision-style documents — fallback sang paragraph)

Không có cấu trúc `Điều` rõ ràng → fallback sang **paragraph chunking**:
- Tách theo `\n\n` (dòng trống)
- Mỗi đoạn ≤ `LEGAL_CHUNK_MAX_CHARS`
- `chunk_level` = `sub_chapter` (vì tài liệu có paragraphs nhưng không phải law-style)

## 2b. Chunk Metadata

Each chunk vector in Qdrant carries the following fields for legal-aware retrieval and filtering:

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

**Relationships field** (`relationships`): Loaded from the dataset's `relationships.parquet` via `doc_id` join. Each entry has `other_doc_id` (linked doc's ID) and `relationship` (type, e.g. `"replaces"`, `"amends"`). Passed through to Qdrant payload for use in legal-aware retrieval or UI display. If a document has no relationships, the field is an empty list `[]`.

## 2c. Thay đổi chunking → Reset checkpoint

Nếu quy tắc chunking thay đổi (ví dụ: `LEGAL_CHUNK_MAX_CHARS` hoặc cấu trúc tách), **phải reset checkpoint** để tránh inconsistency:

```bash
rm data/.ingest_articles.json
# Xóa collection cũ trên Qdrant (tùy chọn, khuyến nghị nếu vector size thay đổi)
# Recreate collection nếu cần
backend/.venv/bin/python scripts/ingest_phapdien.py --reset-checkpoint
```

**Tại sao cần reset?**
- Checkpoint lưu checkpoint cuối cùng của quá trình ingest
- Chunk id/tổng số chunk có thể thay đổi với rule mới
- Vector cũ không tươ thích với chunking mới

## 3. Prerequisites

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

Cần `backend/.env` có tối thiểu:

```env
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=legal_articles
OLLAMA_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3
LEGAL_DATASET_NAME=th1nhng0/vietnamese-legal-documents
LEGAL_DATASET_METADATA_CONFIG=metadata
LEGAL_DATASET_CONTENT_CONFIG=content
LEGAL_DATASET_RELATIONSHIPS_CONFIG=relationships
LEGAL_DATASET_SPLIT=data
LEGAL_CHUNK_MAX_CHARS=1200
```

## 4. Smoke test

```bash
cd /home/khoa/Company/VietNamLaw
backend/.venv/bin/python scripts/ingest_phapdien.py --limit 3 --reset-checkpoint
backend/.venv/bin/python scripts/ingest_phapdien.py --limit 100 --reset-checkpoint
```

Kỳ vọng:
- script load được metadata/content/relationships
- records không có `content_html` sẽ bị skip
- point count có thể lớn hơn số document vì 1 document sinh nhiều chunks

## 5. Verify Qdrant

```bash
cd backend
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
i = c.get_collection(QDRANT_COLLECTION_NAME)
print('points:', i.points_count, 'vector_size:', i.config.params.vectors.size)
"
```

## 6. Verify retrieval

```bash
cd backend
.venv/bin/python - <<'PY'
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import search_legal_context
for item in search_legal_context('Thông tư về công chứng', top_k=3):
    print(item['score'], item['title'], item['source_url'])
PY
```

## 7. Known caveat

Nếu `datasets.load_dataset(..., 'content', split='data')` ném lỗi `ArrowInvalid: Failed casting from large_string to string`, đây là lỗi tương thích hiện tại của toolchain, không phải lỗi data. Script đã tránh đường này bằng cách đọc parquet trực tiếp qua `pyarrow`.
