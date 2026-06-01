# Tiếp tục Ingest Qdrant — Máy khác

## Trạng thái hiện tại

- **Checkpoint**: `index 9438` (last chunk `12030:4`)
- **Qdrant Cloud**: `legal_articles` collection (~148,823+ points)
- **Checkpoint file**: `/home/khoa/Company/VietNamLaw/data/.ingest_articles.json`

## Yêu cầu máy

- Python 3.12+
- Ollama chạy `bge-m3` model
- Internet (HuggingFace + Qdrant Cloud)
- Khuyến nghị: 8GB RAM, 4GB VRAM (GPU embed)

## Các bước trên máy mới

### 1. Clone project
```bash
git clone https://github.com/your-repo/VietNamLaw.git
cd VietNamLaw
```

### 2. Tạo virtualenv và cài đặt
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate

pip install pyarrow datasets huggingface_hub httpx qdrant-client
```

### 3. Cấu hình .env
```bash
cp backend/.env.example backend/.env
# Điền các biến:
#   QDRANT_URL=https://748bb474-da16-472e-afe4-ef8b07fbb2aa.eu-west-1-0.aws.cloud.qdrant.io
#   QDRANT_API_KEY=...
#   OLLAMA_URL=http://localhost:11434
#   OLLAMA_EMBEDDING_MODEL=bge-m3
#   OLLAMA_EMBED_BATCH_SIZE=4
#   INGEST_BATCH_SIZE=20
#   INGEST_CONCURRENT_WORKERS=2
#   HF_TOKEN=... (tùy, không bắt buộc)
```

### 4. Copy checkpoint file
```bash
# Từ máy hiện tại, copy file checkpoint:
scp data/.ingest_articles.json user@máy-mới:/home/khoa/Company/VietNamLaw/data/
```

### 5. Chạy Ollama (nếu chưa có)
```bash
ollama pull bge-m3
ollama serve
```

### 6. Chạy ingest
```bash
cd VietNamLaw
source backend/.venv/bin/activate
nohup python -u scripts/ingest_phapdien.py >> ingest.log 2>&1 &
echo "PID: $!"
```

### 7. Monitor progress
```bash
# Xem log
tail -f /tmp/ingest.log

# Xem checkpoint
cat data/.ingest_articles.json

# Xem Qdrant points
curl -s "https://748bb474-da16-472e-afe4-ef8b07fbb2aa.eu-west-1-0.aws.cloud.qdrant.io/collections/legal_articles" \
  -H "api-key: YOUR_API_KEY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Points: {d[\"result\"][\"points_count\"]}')"
```

## Tốc độ ước tính (aggressive config)

- **Tốc độ**: ~20,000-30,000 docs/giờ
- **Thời gian còn lại**: ~5-8 giờ
- **Còn lại**: ~144,000 documents (từ index 9438)

## Cấu hình aggressive (khuyến nghị)

File `backend/core/config.py`:
```python
OLLAMA_EMBED_BATCH_SIZE = 4    # batch 4 texts/lần
INGEST_BATCH_SIZE = 20          # upsert 20 chunks/lần
INGEST_CONCURRENT_WORKERS = 2    # embed + upsert song song
```

Hoặc điều chỉnh trong `.env`:
```
OLLAMA_EMBED_BATCH_SIZE=4
INGEST_BATCH_SIZE=20
INGEST_CONCURRENT_WORKERS=2
```

## Nếu muốn reset và chạy lại từ đầu

```bash
cd VietNamLaw
source backend/.venv/bin/activate
python -u scripts/ingest_phapdien.py --reset-checkpoint
```

## Kiểm tra Qdrant sau khi xong

```bash
curl -s "https://748bb474-da16-472e-afe4-ef8b07fbb2aa.eu-west-1-0.aws.cloud.qdrant.io/collections/legal_articles" \
  -H "api-key: YOUR_API_KEY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Total points: {d[\"result\"][\"points_count\"]}')"
```