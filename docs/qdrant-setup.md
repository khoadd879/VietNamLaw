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
- `article_anchor`
- `article_title`
- `chapter_title`
- `subject_title`
- `topic_title`
- `source_url`
- `scraped_at`

These 7 fields are all that `search_legal_context` filters on. The other 10
phapdien-moj fields (`content_text`, `content_char_len`, `content_word_count`,
`subject_id`, `subject_number`, `topic_id`, `topic_number`, `source_note_text`,
`related_note_text`, `source_links`) are stored verbatim in payload for display
and audit, but not indexed.

## Verify Connection

```bash
cd backend
python -c "from qdrant_client import QdrantClient; c = QdrantClient(url='YOUR_URL', api_key='YOUR_KEY'); print(c.get_collections())"
```
