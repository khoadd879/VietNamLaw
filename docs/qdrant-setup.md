# Qdrant Cloud Setup

This project uses Qdrant Cloud for vector storage. No local container required.

## Configure Backend

Add to `backend/.env`:

```env
QDRANT_URL=https://xxxxxxx.cloud.qdrant.io
QDRANT_API_KEY=your_api_key_here
QDRANT_COLLECTION_NAME=legal_articles
```

## Collection Schema

The backend creates the collection automatically on first ingest with:
- vector size: `1024`
- distance: `cosine`

Indexed payload fields:
- `title`
- `so_ky_hieu`
- `loai_van_ban`
- `co_quan_ban_hanh`
- `tinh_trang_hieu_luc`
- `linh_vuc`
- `nganh`
- `source_url`

## Verify Connection

```bash
cd backend
python -c "from qdrant_client import QdrantClient; c = QdrantClient(url='YOUR_URL', api_key='YOUR_KEY'); print(c.get_collections())"
```
