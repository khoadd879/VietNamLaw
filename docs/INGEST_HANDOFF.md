# RAG Ingestion Handoff — VietNamLaw

Mục đích: tài liệu để bạn (hoặc bất kỳ ai) **mở repo này trên máy khác và chạy tiếp** quá trình embed dataset `tmquan/phapdien-moj-gov-vn` lên Qdrant Cloud, không cần đọc lại lịch sử chat.

Trạng thái hiện tại tại thời điểm viết file này: pipeline RAG đã hoạt động end-to-end với **Ollama bge-m3 (1024 dims)**, đã smoke test 200 article thành công. Còn lại: chạy ingest full 64,464 article và verify retrieval/chat thật.

---

## 1. Stack hiện tại

- **Backend**: FastAPI (Python 3.11+), code trong `backend/`
- **Frontend**: Next.js 14, code trong `frontend/`
- **DB**: Neon Postgres (auth + chat history)
- **Vector DB**: Qdrant Cloud — collection `legal_articles`, **1024 chiều, cosine**
- **Embedding**: **Ollama `bge-m3`** chạy local tại `http://localhost:11434` (1024 chiều, đa ngôn ngữ)
- **Answer LLM**: Groq với pool 3 keys, fallback nếu cạn
- **Dataset**: HuggingFace `tmquan/phapdien-moj-gov-vn`, split `train`, 64,464 article

Embedding qua Ollama nên **không có rate limit**; bottleneck chỉ là CPU/GPU local.

---

## 2. Yêu cầu trước khi chạy trên máy mới

### 2.1 Hệ điều hành
- Linux hoặc macOS (script `run.sh` viết bằng bash)
- Có Python 3.11+ và Node 18+

### 2.2 Cần cài

1. **Ollama** + model `bge-m3`
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   sudo systemctl enable --now ollama   # Linux
   ollama pull bge-m3
   ```
   Verify:
   ```bash
   curl -s http://localhost:11434/api/tags | head -c 200
   ```
   Phải thấy `bge-m3:latest` trong list.

2. **Backend Python venv** + dependencies
   ```bash
   cd backend
   python3 -m venv .venv
   .venv/bin/pip install -U pip
   .venv/bin/pip install -r requirements.txt
   ```
   Trong `requirements.txt` đã có: `fastapi`, `qdrant-client`, `google-genai`, `groq`, `datasets`, `httpx`, ...

3. **Frontend (chỉ cần khi muốn chạy UI)**
   ```bash
   cd frontend
   npm install
   ```

### 2.3 Credentials trong `backend/.env`

Tạo file `backend/.env` từ `backend/.env.example` và điền các giá trị thật. Các biến quan trọng cho ingest:

```env
# Qdrant Cloud
QDRANT_URL=https://<your-cluster>.qdrant.io
QDRANT_API_KEY=<your-qdrant-api-key>
QDRANT_COLLECTION_NAME=legal_articles

# Embeddings (local Ollama, 1024 dims)
OLLAMA_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3

# Answer generation (Groq pool 3 keys)
GROQ_API_KEY_1=<key 1>
GROQ_API_KEY_2=<key 2>
GROQ_API_KEY_3=<key 3>
GROQ_MODEL=llama-3.1-8b-instant

# Auth + Postgres (chỉ cần khi chạy backend FastAPI thật, không bắt buộc cho ingest)
NEON_DATABASE_URL=postgresql+psycopg://user:password@host/dbname?sslmode=require
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# (giữ lại nếu sau muốn quay về Gemini embedding, không bắt buộc cho Ollama)
GEMINI_API_KEY=<optional>
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

> Chỉ cần `QDRANT_*` và `OLLAMA_*` để ingest. `GROQ_*` và `NEON_*` dành cho khi mở UI chat.

---

## 3. Trước khi ingest: đảm bảo Qdrant collection sạch và đúng dim

Bắt buộc kiểm tra:
- Nếu cluster đã có collection `legal_articles` cũ ở dim ≠ 1024 (ví dụ 768 từ run cũ), phải **xóa và recreate**.
- Nếu cluster trống thì script tự tạo lần đầu khi chạy ingest.

Lệnh xóa collection cũ (nếu cần):

```bash
cd backend
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
existing = [x.name for x in c.get_collections().collections]
if QDRANT_COLLECTION_NAME in existing:
    c.delete_collection(QDRANT_COLLECTION_NAME)
    print('deleted', QDRANT_COLLECTION_NAME)
else:
    print('not found, fresh start')
"
```

Reset checkpoint cũ (nếu có) để ingest lại từ đầu:

```bash
rm -f data/.ingest_checkpoint.json
```

---

## 4. Smoke test trước khi ingest full

Chạy 3 article để verify Ollama + Qdrant nối được với nhau:

```bash
cd /path/to/VietNamLaw
backend/.venv/bin/python scripts/ingest_phapdien.py --limit 3 --reset-checkpoint
```

Kỳ vọng:
- Output `Ingestion complete!` với 3 article
- Không có traceback

Verify số điểm Qdrant + dim:

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

Kỳ vọng: `points: 3 vector_size: 1024`.

Nếu OK, làm tiếp smoke test 200:

```bash
backend/.venv/bin/python scripts/ingest_phapdien.py --limit 200 --reset-checkpoint
```

Kỳ vọng: chạy ~30–60 giây, `points: 200`.

---

## 5. Chạy ingest FULL 64,464 article

Sau khi hai smoke test trên đã pass:

```bash
cd /path/to/VietNamLaw
backend/.venv/bin/python scripts/ingest_phapdien.py --reset-checkpoint
```

Đặc tính:
- Tốc độ tham chiếu: máy CPU thường ~5 article/giây → ~55–60 phút cho toàn bộ dataset. GPU sẽ nhanh hơn.
- Script có **checkpoint** ở `data/.ingest_checkpoint.json`. Nếu bị ngắt (Ctrl+C, mất điện, mất mạng), chạy lại lệnh **không có** `--reset-checkpoint` để resume:
  ```bash
  backend/.venv/bin/python scripts/ingest_phapdien.py
  ```
- Có thể chạy nền:
  ```bash
  nohup backend/.venv/bin/python scripts/ingest_phapdien.py > data/ingest.log 2>&1 &
  tail -f data/ingest.log
  ```

Sau khi xong, verify:

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

Số `points` phải gần 64,464 (có thể nhỏ hơn vài chục vì script bỏ qua các article có `content_text` rỗng).

---

## 6. Verify retrieval

Một vài câu hỏi mẫu để test sau ingest full:

```bash
cd backend
.venv/bin/python - <<'PY'
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import search_legal_context
queries = [
    "Quy định về ly hôn",
    "Trách nhiệm hình sự với người dưới 18 tuổi",
    "Đăng ký kinh doanh hộ cá thể",
    "Thời hiệu khởi kiện hợp đồng dân sự",
]
for q in queries:
    print("Q:", q)
    for r in search_legal_context(q, top_k=3):
        print(" ", round(r["score"], 3), "-", r["article_title"][:80])
PY
```

Khi đủ 64k article, score top-1 thường trên ~0.55–0.70 cho câu hỏi rõ chủ đề. Nếu thấp hơn nhiều thì có khả năng query model/document model bị lệch — kiểm tra lại `OLLAMA_EMBEDDING_MODEL`.

---

## 7. Test backend tự động (tùy chọn)

```bash
cd backend
.venv/bin/python -m pytest
```

Các nhóm test chính:
- `tests/services/test_qdrant_service.py` — embed + search
- `tests/services/test_groq_service.py` — answer + key rotation
- `tests/services/test_startup_schema.py` — startup hook init_db
- `tests/routes/test_chat.py` — auth/contract chat

---

## 8. Chạy frontend + backend cùng lúc

Khi đã có Qdrant đầy dữ liệu:

```bash
bash run.sh
```

- Backend tại `http://localhost:8000`
- Frontend tại `http://localhost:3000`
- Login → tạo session → đặt câu hỏi pháp luật → kiểm tra `reply` và `sources`

---

## 9. Troubleshooting

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Could not connect to localhost:11434` | Daemon Ollama chưa chạy | `sudo systemctl start ollama` |
| `model bge-m3 not found` từ Ollama | Chưa pull model | `ollama pull bge-m3` |
| `relation "users" does not exist` khi login | Schema Postgres chưa tạo | Backend đã tự gọi `init_db()` ở startup; chỉ cần restart backend |
| `Unknown split "articles"` từ HuggingFace | Dataset đổi split | Script đã dùng split `train`. Nếu dataset đổi tên split lần nữa, sửa `scripts/ingest_phapdien.py` chỗ `load_dataset(...)` |
| Qdrant `400 Bad Request: not a valid point ID` | Article anchor không phải UUID/int | Script đã chuyển ID sang `uuid5(NAMESPACE_URL, "phapdien:<anchor>")`. Đừng đổi lại |
| Qdrant `Vector dimension error` | Collection cũ ≠ 1024 | Xóa collection rồi recreate (xem mục 3) |
| `429 RESOURCE_EXHAUSTED` từ Gemini | Vô tình embed qua Gemini thay vì Ollama | Kiểm tra `OLLAMA_*` đã set, code embed đang dùng `services.qdrant_service.embed_texts` qua HTTP Ollama |
| Ollama embed rất chậm | Đang chạy CPU, model float16 nặng | Cài CUDA + GPU driver, hoặc chuyển sang model nhẹ hơn (xem mục 10) |

---

## 10. Đổi sang model embedding khác (tùy chọn)

Nếu sau này muốn đổi sang model embedding khác, ví dụ `nomic-embed-text` (768 chiều) hoặc `granite-embedding` (768 chiều), cần làm đồng thời:

1. `ollama pull <model>`
2. Sửa `OLLAMA_EMBEDDING_MODEL` trong `.env`
3. Sửa `VectorParams(size=...)` trong `backend/services/qdrant_service.py:ensure_collection_exists` cho đúng dim
4. Xóa collection `legal_articles` cũ
5. Reset checkpoint
6. Chạy lại ingest từ đầu

> Lưu ý quan trọng: **document và query bắt buộc dùng cùng một model**. Đừng ingest bằng model A rồi search bằng model B.

---

## 11. Tóm tắt lệnh tối thiểu để chạy tiếp trên máy mới

```bash
# 1. Cài Ollama + model
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull bge-m3

# 2. Setup backend venv
cd /path/to/VietNamLaw
cd backend
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
cd ..

# 3. Tạo backend/.env (xem mục 2.3) — tối thiểu cần QDRANT_* và OLLAMA_*

# 4. (chỉ cần lần đầu trên cluster Qdrant mới hoặc khi đổi dim)
#    Xóa collection cũ — xem snippet ở mục 3

# 5. Smoke test
backend/.venv/bin/python scripts/ingest_phapdien.py --limit 3 --reset-checkpoint
backend/.venv/bin/python scripts/ingest_phapdien.py --limit 200 --reset-checkpoint

# 6. Ingest full
backend/.venv/bin/python scripts/ingest_phapdien.py --reset-checkpoint

# 7. Verify
cd backend && .venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
i = c.get_collection(QDRANT_COLLECTION_NAME)
print('points:', i.points_count, 'vector_size:', i.config.params.vectors.size)
"

# 8. Chạy app
cd .. && bash run.sh
```
