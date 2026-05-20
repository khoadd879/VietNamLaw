# RAG Ingestion Handoff — VietNamLaw

## Current State (2026-05-19)

**Progress:** 21,484 / 64,464 articles (33.3%) ingested
**Checkpoint:** index 21,559 (last processed ID: `#190030000000000050000320000000000000000000402864100100004300`)
**Qdrant Collection:** `legal_articles` — 1024 dims, cosine similarity
**Embedding Model:** Ollama `bge-m3` (local, 1024 dims)

---

## Prerequisites on New Machine

```bash
# 1. Ollama + model
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull bge-m3

# 2. Backend venv
cd VietNamLaw/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Credentials in backend/.env (copy from backend/.env.example)
# Required: QDRANT_URL, QDRANT_API_KEY, OLLAMA_URL, OLLAMA_EMBEDDING_MODEL
```

---

## Continue Ingestion

```bash
cd /home/khoa/Company/VietNamLaw
backend/.venv/bin/python scripts/ingest_phapdien.py
```

Script will auto-resume from checkpoint at `data/.ingest_checkpoint.json`.

---

## Monitor Progress

```bash
# Check Qdrant points
backend/.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
i = c.get_collection(QDRANT_COLLECTION_NAME)
print(f'{i.points_count}/64464 ({(i.points_count/64464)*100:.1f}%)')
"

# Check checkpoint
cat data/.ingest_checkpoint.json
```

---

## If Issues

| Issue | Solution |
|-------|----------|
| `No address associated with hostname` | Network/DNS issue — retry |
| `ReadTimeout` on Ollama | Increase `_EMBED_TIMEOUT_SECONDS` in `backend/services/qdrant_service.py` |
| Qdrant collection wrong dim | Delete and recreate collection |

---

## After Complete

```bash
# Verify
backend/.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
c = get_qdrant_client()
i = c.get_collection(QDRANT_COLLECTION_NAME)
print(f'Final: {i.points_count} points, {i.config.params.vectors.size} dims')
"

# Run app
cd .. && bash run.sh
```