# Qdrant Ingest Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete and verify the Vietnamese legal document ingestion pipeline so chunked records are embedded and upserted into Qdrant with the expected payload fields, including relationships metadata.

**Architecture:** The current pipeline already loads metadata/content/relationships, cleans HTML, chunks legal text, embeds via Ollama, and upserts to Qdrant. The missing work is to carry `relationships` through to Qdrant payloads, add regression coverage for that payload contract, and run an end-to-end smoke ingestion against the configured services.

**Tech Stack:** Python, FastAPI service modules, Hugging Face datasets/parquet, PyArrow, Ollama embeddings, Qdrant, pytest

---

## File map

- Modify: `backend/services/qdrant_service.py` — persist complete ingest payload fields into Qdrant points.
- Modify: `backend/tests/services/test_qdrant_service.py` — add payload regression tests for `relationships` and collection index expectations.
- Modify: `scripts/ingest_phapdien.py` — only if smoke verification exposes an integration mismatch during ingestion.
- Modify: `docs/INGEST_HANDOFF.md` — document the final payload contract if code changes alter the expected metadata.
- Modify: `docs/INGEST_RESUME.md` — keep operator instructions aligned with the implemented payload contract.

## Current audit summary

The pipeline is already present and mostly runnable:

- `scripts/ingest_phapdien.py:94-131` builds chunk records with `relationships` included.
- `scripts/ingest_phapdien.py:199-205` flushes those records into `ingest_articles(...)`.
- `backend/services/qdrant_service.py:275-317` embeds and upserts points into Qdrant.
- `backend/services/qdrant_service.py:287-303` does **not** include `relationships` in the stored payload, so one field produced by the ingest script is silently dropped.
- Existing tests cover chunking, embedding calls, and core payload fields, but do not assert the `relationships` field is preserved.

That means chunking, embedding, and upsert are implemented, but the ingest payload is not fully preserved end to end yet.

### Task 1: Add failing regression test for relationships payload

**Files:**
- Modify: `backend/tests/services/test_qdrant_service.py`
- Test: `backend/tests/services/test_qdrant_service.py`

- [ ] **Step 1: Add a failing payload regression test**

```python
def test_ingest_articles_stores_relationships_on_payload() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "total_chunks": 2,
        "chunk_level": "article",
        "chapter_label": "Chương I",
        "article_label": "Điều 1",
        "content_text": "Điều 1. Nội dung thử nghiệm.",
        "title": "Luật mẫu",
        "so_ky_hieu": "01/2026/QH",
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "linh_vuc": "Dân sự",
        "nganh": "Tư pháp",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "relationships": [
            {
                "other_doc_id": "456",
                "relationship": "references",
            }
        ],
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point.payload["relationships"] == [
        {
            "other_doc_id": "456",
            "relationship": "references",
        }
    ]
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `backend/.venv/bin/pytest backend/tests/services/test_qdrant_service.py::test_ingest_articles_stores_relationships_on_payload -v`
Expected: FAIL with `KeyError: 'relationships'` or equivalent missing-payload assertion.

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/services/test_qdrant_service.py
git commit -m "test: cover qdrant relationships payload"
```

### Task 2: Persist relationships in Qdrant payload

**Files:**
- Modify: `backend/services/qdrant_service.py:281-303`
- Test: `backend/tests/services/test_qdrant_service.py`

- [ ] **Step 1: Update the Qdrant payload mapping**

Replace the payload block inside `PointStruct(...)` with:

```python
payload={
    "content_text": article["content_text"],
    "title": article["title"],
    "doc_id": article["doc_id"],
    "chunk_index": article["chunk_index"],
    "so_ky_hieu": article.get("so_ky_hieu", ""),
    "loai_van_ban": article.get("loai_van_ban", ""),
    "co_quan_ban_hanh": article.get("co_quan_ban_hanh", ""),
    "tinh_trang_hieu_luc": article.get("tinh_trang_hieu_luc", ""),
    "linh_vuc": article.get("linh_vuc", ""),
    "nganh": article.get("nganh", ""),
    "source_url": article["source_url"],
    "chapter_label": article.get("chapter_label"),
    "article_label": article.get("article_label"),
    "chunk_level": article.get("chunk_level", "paragraph"),
    "total_chunks": article.get("total_chunks"),
    "relationships": article.get("relationships", []),
}
```

- [ ] **Step 2: Run the targeted regression test to verify it passes**

Run: `backend/.venv/bin/pytest backend/tests/services/test_qdrant_service.py::test_ingest_articles_stores_relationships_on_payload -v`
Expected: PASS

- [ ] **Step 3: Run the broader Qdrant service test file**

Run: `backend/.venv/bin/pytest backend/tests/services/test_qdrant_service.py -v`
Expected: PASS for all Qdrant service tests.

- [ ] **Step 4: Commit the implementation**

```bash
git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py
git commit -m "feat: preserve legal relationships in qdrant payload"
```

### Task 3: Verify collection setup and ingestion contract

**Files:**
- Modify: `backend/tests/services/test_qdrant_service.py`
- Modify: `docs/INGEST_HANDOFF.md`
- Modify: `docs/INGEST_RESUME.md`

- [ ] **Step 1: Add a collection contract test for payload indexes if the project expects filterable relationships later**

If relationships should only be stored and not filtered, skip index creation changes and add this test instead:

```python
def test_ensure_collection_exists_creates_expected_payload_indexes() -> None:
    from services.qdrant_service import ensure_collection_exists

    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])

    ensure_collection_exists(mock_client)

    created_indexes = [
        call.kwargs["field_name"]
        for call in mock_client.create_payload_index.call_args_list
    ]
    assert created_indexes == [
        "title",
        "so_ky_hieu",
        "loai_van_ban",
        "co_quan_ban_hanh",
        "tinh_trang_hieu_luc",
        "linh_vuc",
        "nganh",
        "source_url",
        "chapter_label",
        "article_label",
        "chunk_level",
    ]
```

- [ ] **Step 2: Run the new contract test**

Run: `backend/.venv/bin/pytest backend/tests/services/test_qdrant_service.py::test_ensure_collection_exists_creates_expected_payload_indexes -v`
Expected: PASS

- [ ] **Step 3: Update operator docs to mention relationships are now stored in payload**

Add this field to the sample payload blocks in both docs:

```json
"relationships": [
  {
    "other_doc_id": "<string>",
    "relationship": "<string>"
  }
]
```

- [ ] **Step 4: Verify docs remain aligned with implemented behavior**

Read these sections after editing and confirm they match code:
- `docs/INGEST_HANDOFF.md:17-30`
- `docs/INGEST_RESUME.md:53-66`

- [ ] **Step 5: Commit the contract updates**

```bash
git add backend/tests/services/test_qdrant_service.py docs/INGEST_HANDOFF.md docs/INGEST_RESUME.md
git commit -m "docs: align ingest contract with stored qdrant payload"
```

### Task 4: Run end-to-end smoke ingestion

**Files:**
- Modify: `scripts/ingest_phapdien.py` only if smoke test exposes a real integration defect
- Test: live Qdrant collection and Ollama endpoint

- [ ] **Step 1: Verify runtime prerequisites**

Run: `backend/.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from core.config import QDRANT_API_KEY, OLLAMA_URL, OLLAMA_EMBEDDING_MODEL; print(bool(QDRANT_API_KEY), OLLAMA_URL, OLLAMA_EMBEDDING_MODEL)"`
Expected: `True` for the Qdrant key, plus the configured Ollama URL/model.

- [ ] **Step 2: Run a small reset smoke ingest**

Run: `backend/.venv/bin/python scripts/ingest_phapdien.py --limit 3 --reset-checkpoint`
Expected: metadata/content/relationships load successfully, several chunks are upserted, and a new `data/.ingest_articles.json` checkpoint is written.

- [ ] **Step 3: Inspect the Qdrant collection after smoke ingest**

Run: `backend/.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from services.qdrant_service import get_qdrant_client; from core.config import QDRANT_COLLECTION_NAME; c = get_qdrant_client(); i = c.get_collection(QDRANT_COLLECTION_NAME); print(f'points: {i.points_count}, vector_size: {i.config.params.vectors.size}')"`
Expected: positive point count and vector size `1024`.

- [ ] **Step 4: Inspect one stored point payload and confirm relationships are present**

Run: `backend/.venv/bin/python - <<'PY'
from dotenv import load_dotenv
load_dotenv()
from services.qdrant_service import get_qdrant_client
from core.config import QDRANT_COLLECTION_NAME
client = get_qdrant_client()
points, _ = client.scroll(collection_name=QDRANT_COLLECTION_NAME, limit=1, with_payload=True, with_vectors=False)
print(points[0].payload)
PY`
Expected: payload includes `content_text`, legal metadata fields, and `relationships`.

- [ ] **Step 5: Run retrieval smoke test**

Run: `backend/.venv/bin/python - <<'PY'
from dotenv import load_dotenv
load_dotenv()
from services.qdrant_service import search_legal_context
for item in search_legal_context('Thông tư về công chứng', top_k=3):
    print(item['score'], item['title'], item['source_url'])
PY`
Expected: returns scored results without embedding or Qdrant errors.

- [ ] **Step 6: If smoke ingest fails, patch the exact failing integration point and rerun only the failing step**

Use one of these minimal-change patterns depending on the observed failure:

```python
# If a payload key is missing in build_chunk_records(...)
"relationships": relationships,
```

```python
# If a flushed batch size is too large for the local embed server, lower env config instead of changing logic
INGEST_BATCH_SIZE=5
```

```python
# If Ollama times out under real load, increase the existing timeout constant
_EMBED_TIMEOUT_SECONDS = 600.0
```

- [ ] **Step 7: Commit any integration fix only if a real code change was required**

```bash
git add scripts/ingest_phapdien.py backend/services/qdrant_service.py backend/core/config.py
git commit -m "fix: stabilize qdrant smoke ingestion"
```

### Task 5: Run production ingestion with five teammates

**Files:**
- No mandatory code changes
- Operational task using agent teammates and shell execution

- [ ] **Step 1: Partition the work before spawning teammates**

Use five independent ranges so agents do not duplicate ingestion work:

```text
teammate-1: metadata indexes 0-19999
teammate-2: metadata indexes 20000-39999
teammate-3: metadata indexes 40000-59999
teammate-4: metadata indexes 60000-79999
teammate-5: metadata indexes 80000-end
```

- [ ] **Step 2: Add range support before parallel execution if the script does not already support it**

Add CLI arguments like:

```python
parser.add_argument("--start-index", type=int, default=0)
parser.add_argument("--end-index", type=int, default=None)
```

and change the main loop to:

```python
start_index = max(start_index, args.start_index)
end_index = total_documents if args.end_index is None else min(args.end_index, total_documents)

for i in range(start_index, end_index):
    ...
```

- [ ] **Step 3: Give each teammate an isolated checkpoint path before parallel execution**

Add CLI support like:

```python
parser.add_argument("--checkpoint-path", type=Path, default=get_checkpoint_path())
```

and thread it through:

```python
checkpoint = None if args.reset_checkpoint else load_checkpoint(args.checkpoint_path)
...
save_checkpoint(i, last_record_id, args.checkpoint_path)
```

- [ ] **Step 4: Verify the new range/checkpoint behavior with one targeted test and one smoke run**

Run: `backend/.venv/bin/pytest backend/tests/services/test_checkpoint.py -v`
Expected: PASS

Run: `backend/.venv/bin/python scripts/ingest_phapdien.py --limit 2 --start-index 0 --end-index 2 --checkpoint-path data/.ingest-smoke.json --reset-checkpoint`
Expected: PASS and writes `data/.ingest-smoke.json`.

- [ ] **Step 5: Spawn five teammates only after Tasks 1-4 are green**

Each teammate should run one disjoint range with its own checkpoint file:

```bash
backend/.venv/bin/python scripts/ingest_phapdien.py --start-index 0 --end-index 20000 --checkpoint-path data/.ingest-1.json --reset-checkpoint
backend/.venv/bin/python scripts/ingest_phapdien.py --start-index 20000 --end-index 40000 --checkpoint-path data/.ingest-2.json --reset-checkpoint
backend/.venv/bin/python scripts/ingest_phapdien.py --start-index 40000 --end-index 60000 --checkpoint-path data/.ingest-3.json --reset-checkpoint
backend/.venv/bin/python scripts/ingest_phapdien.py --start-index 60000 --end-index 80000 --checkpoint-path data/.ingest-4.json --reset-checkpoint
backend/.venv/bin/python scripts/ingest_phapdien.py --start-index 80000 --checkpoint-path data/.ingest-5.json --reset-checkpoint
```

- [ ] **Step 6: Monitor total points rather than per-document counts**

Run: `backend/.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from services.qdrant_service import get_qdrant_client; from core.config import QDRANT_COLLECTION_NAME; c = get_qdrant_client(); i = c.get_collection(QDRANT_COLLECTION_NAME); print(f'points: {i.points_count}')"`
Expected: point count increases over time.

- [ ] **Step 7: Commit the operational script support if range/checkpoint flags were added**

```bash
git add scripts/ingest_phapdien.py backend/tests/services/test_checkpoint.py docs/INGEST_HANDOFF.md docs/INGEST_RESUME.md
git commit -m "feat: support parallel legal corpus ingestion"
```

## Self-review

- Spec coverage: covered code audit, missing payload persistence, regression tests, smoke verification, and the user-requested five-teammate execution path.
- Placeholder scan: no TODO/TBD placeholders remain; commands, file paths, and code snippets are explicit.
- Type consistency: `relationships` is represented consistently as `list[dict[str, str]]`; range arguments use integers; checkpoint path uses `Path`.

Plan complete and saved to `docs/superpowers/plans/2026-05-22-qdrant-ingest-gap-closure.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
