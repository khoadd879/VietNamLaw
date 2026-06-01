# Store Whole `phapdien-moj` Articles (No Chunking) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop chunking the `tmquan/phapdien-moj-gov-vn` dataset. Store each row as exactly one Qdrant point with all 17 source fields preserved as payload. No synthetic `chunk_*` / `*_label` fields. Drop dead legacy code (`crossref_walker`, `relationships`, `article_label`/`chapter_label`/`chunk_*`/`loai_van_ban` fallbacks) and trim `search_legal_context` return shape to what consumers actually read.

**Architecture:**
- **Qdrant payload** (stored): all 17 phapdien-moj fields, verbatim. `id` is `uuid5(NAMESPACE_URL, f"phapdien:{article_anchor.lstrip('#')}")`.
- **API return** (`search_legal_context`, `bm25_index._scroll_all_points`): only `id`, `content_text`, `title` (from `article_title`), `source_url`, `score` (+ `bm25_score` for BM25). 5 fields, not 24.
- **Removed entirely:** `crossref_walker.py`, `relationships` payload field, `CROSSREF_MAX_HOPS`/`CROSSREF_MAX_CHUNKS` config, the `walk_relationships` call in `chat_service`, all `article_label`/`chapter_label`/`chunk_index`/`chunk_level`/`total_chunks`/`loai_van_ban`/`co_quan_ban_hanh`/`tinh_trang_hieu_luc`/`doc_id` legacy fallbacks in the 3 service files.
- **Kept (used by retrieval / display):** `content_text`, `article_title`, `chapter_title`, `subject_title`, `topic_title`, `source_url`, `source_note_text`, `related_note_text`, `source_links` — all stored in Qdrant payload, but only surfaced through the LLM context when needed.

**Tech Stack:** Python, `datasets` (HuggingFace), `qdrant-client`, `bge-m3` via Ollama, `pytest`.

**Spec:** `docs/superpowers/specs/2026-06-01-store-whole-phapdien-articles-no-chunking.md`

---

## File Map

| File | Change |
| --- | --- |
| `scripts/ingest_phapdien_moj.py` | Replace `build_chunk_records` with `build_point_record`; 1 row → 1 record |
| `backend/services/qdrant_service.py` | `ingest_articles` accepts new schema; `ensure_collection_exists` indexes new fields; `search_legal_context` returns only 5 fields; **remove** `HTMLLegalParser`, `split_legal_chunks`, `split_document_chunks`, `clean_html_text`, `detect_doc_format`, `_HTMLLegalParserImpl` (dead code — only the legacy th1nhng0 ingest uses them, and even there they're optional) |
| `backend/services/bm25_index.py` | Read `article_title` only; return `id`, `content_text`, `title`, `source_url` |
| `backend/services/crossref_walker.py` | **DELETE** |
| `backend/services/chat_service.py` | Remove `walk_relationships` import and call |
| `backend/core/config.py` | Add `PHAPDIEN_MAX_CONTENT_CHARS`; **remove** `CROSSREF_MAX_HOPS`, `CROSSREF_MAX_CHUNKS`; **remove unused** `LEGAL_ARTICLE_CHAPTER_THRESHOLD` |
| `backend/tests/services/test_qdrant_service.py` | Update tests for new schema; add new test for full-field ingest; remove chunking tests |
| `backend/tests/services/test_bm25_index.py` | Update field fallback test → simple 5-field test |
| `backend/tests/services/test_crossref_walker.py` | **DELETE** |
| `docs/qdrant-setup.md` | Update indexed-fields list |

---

## Task 1: Add `PHAPDIEN_MAX_CONTENT_CHARS` and remove crossref config

**Files:**
- Modify: `backend/core/config.py:21-22, 51-52`

- [ ] **Step 1: Replace the config block**

Replace lines 21-22 and 51-52 with:

```python
PHAPDIEN_MAX_CONTENT_CHARS = int(os.getenv("PHAPDIEN_MAX_CONTENT_CHARS", "10000"))
```

And delete lines 51-52 (`CROSSREF_MAX_HOPS` and `CROSSREF_MAX_CHUNKS`).

- [ ] **Step 2: Verify no other code references the removed config**

Run: `cd backend && grep -rn "CROSSREF_MAX_HOPS\|CROSSREF_MAX_CHUNKS" . 2>&1 | grep -v __pycache__`
Expected: no matches (will be cleaned in later tasks).

If matches exist in test files, note them; they will be removed when test files are rewritten.

- [ ] **Step 3: Commit**

```bash
git add backend/core/config.py
git commit -m "feat(config): add PHAPDIEN_MAX_CONTENT_CHARS, drop crossref config"
```

---

## Task 2: Add failing tests for `ingest_articles` full-field payload

**Files:**
- Modify: `backend/tests/services/test_qdrant_service.py` (append near end)

- [ ] **Step 1: Write test that asserts all 17 phapdien-moj fields land in payload**

Append to `test_qdrant_service.py`:

```python
def test_ingest_articles_preserves_all_phapdien_moj_fields() -> None:
    from services.qdrant_service import ingest_articles

    row = {
        "id": "0100100000000000100000100000000000000000",
        "article_anchor": "#0100100000000000100000100000000000000000",
        "article_title": "Điều 1.1.LQ.1. Phạm vi điều chỉnh",
        "content_text": "Luật này quy định về chính sách an ninh quốc gia.",
        "content_char_len": 65,
        "content_word_count": 14,
        "chapter_title": "Chương I - NHỮNG QUY ĐỊNH CHUNG",
        "subject_id": "55323c64-e78f-4537-afcd-6a3c2af3c71d",
        "subject_number": 1,
        "subject_title": "An ninh quốc gia",
        "topic_id": "c3b69131-2931-4f67-926e-b244e18e8081",
        "topic_number": 1,
        "topic_title": "An ninh quốc gia",
        "source_note_text": "(Điều 1 Luật số 32/2004/QH11)",
        "source_links": [{"text": "link", "href": "http://vbpl.vn/x"}],
        "related_note_text": "Liên quan đến Điều 1.12.LQ.11",
        "source_url": "https://phapdien.moj.gov.vn/TraCuuPhapDien/ViewBoPD.aspx?obj=&demucid=55323c64",
        "scraped_at": "2026-05-08T15:49:05+00:00",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            ingest_articles([row])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    payload = point.payload

    # All 17 source fields must be present with exact same value
    for key, expected in row.items():
        if key == "id":
            continue  # id is the qdrant uuid, not payload
        assert payload.get(key) == expected, f"Missing or wrong payload[{key!r}]"

    # No synthetic chunk_* / *_label / relationships / doc_id / title-alias
    for forbidden in ("chunk_index", "total_chunks", "chunk_level",
                      "chapter_label", "article_label", "khoan_label",
                      "title", "relationships", "doc_id",
                      "so_ky_hieu", "loai_van_ban", "co_quan_ban_hanh",
                      "tinh_trang_hieu_luc", "linh_vuc", "nganh"):
        assert forbidden not in payload, f"Forbidden field {forbidden!r} in payload"


def test_ingest_articles_id_is_deterministic_uuid5() -> None:
    from services.qdrant_service import ingest_articles
    from uuid import NAMESPACE_URL, uuid5

    row = {
        "id": "0100100000000000100000100000000000000000",
        "article_anchor": "#0100100000000000100000100000000000000000",
        "article_title": "Điều 1. Phạm vi",
        "content_text": "Nội dung",
        "source_url": "https://phapdien.moj.gov.vn/x",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            ingest_articles([row])

    expected_id = str(uuid5(NAMESPACE_URL, f"phapdien:{row['article_anchor'].lstrip('#')}"))
    assert str(mock_client.upsert.call_args.kwargs["points"][0].id) == expected_id
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_qdrant_service.py::test_ingest_articles_preserves_all_phapdien_moj_fields tests/services/test_qdrant_service.py::test_ingest_articles_id_is_deterministic_uuid5 -v`
Expected: FAIL (old `ingest_articles` looks for `chunk_index`, drops fields, renames to `chapter_label`/`article_label`).

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/services/test_qdrant_service.py
git commit -m "test(qdrant): assert full phapdien-moj field preservation in payload"
```

---

## Task 3: Rewrite `ingest_articles` to passthrough phapdien-moj schema

**Files:**
- Modify: `backend/services/qdrant_service.py:558-607` (the `ingest_articles` function)

- [ ] **Step 1: Replace the `ingest_articles` body**

Replace the entire function (lines 558-607) with:

```python
def ingest_articles(articles: list[dict], batch_size: int | None = None) -> None:
    """Embed a batch of phapdien-moj records and upsert as Qdrant points.

    Each input record becomes exactly one Qdrant point. The record is passed
    through to payload verbatim, with the only filtering being a type check:
    scalars (str/int/float/bool/None) and lists-of-dicts (for ``source_links``)
    are forwarded; everything else is dropped to keep the payload serializable.
    No synthetic fields are added.

    The Qdrant point id is ``uuid5(NAMESPACE_URL, f"phapdien:{anchor}")`` where
    ``anchor`` is ``article_anchor`` with any leading ``#`` stripped.
    """
    if batch_size is None:
        batch_size = INGEST_BATCH_SIZE
    client = get_qdrant_client()
    workers = INGEST_CONCURRENT_WORKERS

    _SCALAR_TYPES = (str, int, float, bool, type(None))

    def _coerce_payload(article: dict) -> dict:
        out: dict = {}
        for key, value in article.items():
            if key == "id":
                continue
            if isinstance(value, _SCALAR_TYPES):
                out[key] = value
            elif isinstance(value, list) and all(isinstance(x, dict) for x in value):
                out[key] = value
        return out

    def _embed_and_build(article: dict) -> PointStruct:
        vector = embed_texts([article["content_text"]], task_type="RETRIEVAL_DOCUMENT")[0]
        anchor = article["article_anchor"].lstrip("#")
        point_id = str(uuid5(NAMESPACE_URL, f"phapdien:{anchor}"))
        return PointStruct(id=point_id, vector=vector, payload=_coerce_payload(article))

    points = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_embed_and_build, art): art for art in articles}
        for future in as_completed(futures):
            points.append(future.result())

    max_retries = 5
    for attempt in range(max_retries):
        try:
            client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points)
            return
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  [upsert retry {attempt + 1}/{max_retries}] {exc} — waiting {wait}s")
            time.sleep(wait)
```

- [ ] **Step 2: Run new tests, verify they pass**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_qdrant_service.py::test_ingest_articles_preserves_all_phapdien_moj_fields tests/services/test_qdrant_service.py::test_ingest_articles_id_is_deterministic_uuid5 -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/services/qdrant_service.py
git commit -m "feat(qdrant): passthrough phapdien-moj fields, no synthetic metadata"
```

---

## Task 4: Trim `search_legal_context` to the 5 fields consumers actually read

**Files:**
- Modify: `backend/services/qdrant_service.py:610-658` (`search_legal_context`)

- [ ] **Step 1: Add failing test for the trimmed return shape**

Append to `test_qdrant_service.py`:

```python
def test_search_legal_context_returns_only_consumed_fields() -> None:
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.id = "uuid-1"
    mock_point.payload = {
        "content_text": "Luật này quy định...",
        "article_title": "Điều 1. Phạm vi",
        "source_url": "https://phapdien.moj.gov.vn/x",
        # The rest of the 17 fields are present in Qdrant but not exposed:
        "article_anchor": "#01001",
        "chapter_title": "Chương I",
        "subject_title": "An ninh quốc gia",
        "topic_title": "An ninh quốc gia",
        "scraped_at": "2026-05-08T15:49:05+00:00",
        "subject_id": "uuid-x",
        "topic_id": "uuid-y",
        "source_note_text": "...",
        "related_note_text": "...",
        "source_links": [{"text": "t", "href": "h"}],
        "content_char_len": 50,
        "content_word_count": 10,
    }
    mock_point.score = 0.9

    mock_response = MagicMock()
    mock_response.points = [mock_point]

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client
        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            results = search_legal_context(message="Phạm vi điều chỉnh")

    assert len(results) == 1
    r = results[0]
    # Exactly these 5 keys, nothing else
    assert set(r.keys()) == {"id", "content_text", "title", "source_url", "score"}
    assert r["id"] == "uuid-1"
    assert r["title"] == "Điều 1. Phạm vi"
    assert r["source_url"] == "https://phapdien.moj.gov.vn/x"
    assert r["score"] == 0.9
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_qdrant_service.py::test_search_legal_context_returns_only_consumed_fields -v`
Expected: FAIL (old `search_legal_context` returns ~20 fields).

- [ ] **Step 3: Replace the result-construction block in `search_legal_context`**

In `qdrant_service.py`, replace the list-comprehension at lines 640-658 with:

```python
    return [
        {
            "id": str(point.id),
            "content_text": point.payload.get("content_text", ""),
            "title": point.payload.get("article_title", ""),
            "source_url": point.payload.get("source_url", ""),
            "score": point.score,
        }
        for point in results
    ]
```

- [ ] **Step 4: Run new test, verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_qdrant_service.py::test_search_legal_context_returns_only_consumed_fields -v`
Expected: PASS.

- [ ] **Step 5: Remove the now-stale equality tests**

The following tests in `test_qdrant_service.py` hard-code the old 20-field return shape. Delete them (or replace with a one-line assertion of the new shape):

- `test_search_legal_context_returns_vbpl_fields` (lines 138-185)
- `test_search_legal_context_returns_phapdien_moj_fields` (added in old plan, but actually never added yet — skip)
- `test_search_legal_context_returns_relationships` (lines 482-517)
- `test_search_legal_context_returns_empty_relationships_when_missing` (lines 520-552)
- `test_search_legal_context_returns_legal_chunk_metadata_fields` (lines 555-602)

Replace each with a 1-line trim check (e.g. `assert set(r.keys()) == {"id", "content_text", "title", "source_url", "score"}`). Use the test from Step 1 as the canonical shape and remove duplicates.

- [ ] **Step 6: Commit**

```bash
git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py
git commit -m "refactor(qdrant): trim search_legal_context return to 5 consumed fields"
```

---

## Task 5: Simplify `bm25_index` to the 5-field shape

**Files:**
- Modify: `backend/services/bm25_index.py:25-65`

- [ ] **Step 1: Add failing test**

Append to `backend/tests/services/test_bm25_index.py`:

```python
def test_scroll_all_points_returns_5_field_shape() -> None:
    from services.bm25_index import _scroll_all_points

    fake_point = MagicMock()
    fake_point.id = "point-uuid"
    fake_point.payload = {
        "content_text": "Nội dung điều luật",
        "article_title": "Điều 1. Phạm vi",
        "source_url": "https://phapdien.moj.gov.vn/x",
    }

    with patch("services.bm25_index.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.scroll.return_value = ([fake_point], None)
        mock_get_client.return_value = mock_client
        docs = list(_scroll_all_points())

    assert len(docs) == 1
    assert set(docs[0].keys()) == {"id", "content_text", "title", "source_url"}
    assert docs[0]["title"] == "Điều 1. Phạm vi"
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_bm25_index.py::test_scroll_all_points_returns_5_field_shape -v`
Expected: FAIL.

- [ ] **Step 3: Replace `_scroll_all_points` with the 5-field version**

In `bm25_index.py`, replace the entire `_scroll_all_points` function (lines 25-50) with:

```python
def _scroll_all_points(batch_size: int = 200) -> Iterable[dict]:
    """Yield every point in the Qdrant collection as a 5-field dict.

    Returned keys: ``id``, ``content_text``, ``title`` (from ``article_title``),
    ``source_url``. These are the only fields consumed by hybrid_search and
    the LLM context. Extra Qdrant payload fields are ignored.
    """
    client = get_qdrant_client()
    offset = None
    while True:
        result = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = result
        for point in points:
            yield {
                "id": str(point.id),
                "content_text": point.payload.get("content_text", ""),
                "title": point.payload.get("article_title", ""),
                "source_url": point.payload.get("source_url", ""),
            }
        if next_offset is None:
            break
        offset = next_offset
```

- [ ] **Step 4: Run, verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_bm25_index.py -v`
Expected: PASS. Other existing tests in the file will need the new shape too — update any that hard-code `loai_van_ban` / `article_label` / `chapter_label` in expected dicts.

- [ ] **Step 5: Commit**

```bash
git add backend/services/bm25_index.py backend/tests/services/test_bm25_index.py
git commit -m "refactor(bm25): trim scroll output to 5 consumed fields"
```

---

## Task 6: Delete `crossref_walker` and remove its call site

**Files:**
- Delete: `backend/services/crossref_walker.py`
- Delete: `backend/tests/services/test_crossref_walker.py`
- Modify: `backend/services/chat_service.py:3, 122-131`

- [ ] **Step 1: Delete the service file**

Run: `rm backend/services/crossref_walker.py`

- [ ] **Step 2: Delete the test file**

Run: `rm backend/tests/services/test_crossref_walker.py`

- [ ] **Step 3: Remove import and call from `chat_service.py`**

In `chat_service.py`:

- Line 3: delete `from services.crossref_walker import walk_relationships`
- Lines 122-131: delete the entire `if contexts: related = walk_relationships(contexts) ... seen_ids.add(rid)` block

The block to delete (verbatim):

```python
    # SPRINT 3: cross-ref walker
    if contexts:
        related = walk_relationships(contexts)
        # Dedupe against existing contexts
        seen_ids = {c.get("id") or c.get("doc_id") for c in contexts}
        for r in related:
            rid = r.get("id") or r.get("doc_id")
            if rid and rid not in seen_ids:
                contexts.append(r)
                seen_ids.add(rid)
```

- [ ] **Step 4: Verify no other references**

Run: `cd backend && grep -rn "walk_relationships\|crossref_walker" . 2>&1 | grep -v __pycache__`
Expected: no matches.

- [ ] **Step 5: Run chat_service tests**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_chat_service.py tests/test_chat_service.py 2>&1 | tail -20`
Expected: PASS (if tests mock `walk_relationships`, remove the mock too).

- [ ] **Step 6: Commit**

```bash
git add -A backend/
git commit -m "refactor: delete crossref_walker (no relationships data in phapdien-moj)"
```

---

## Task 7: Update `ensure_collection_exists` to index new fields

**Files:**
- Modify: `backend/services/qdrant_service.py:186-198` (constant) and `434-451` (function)

- [ ] **Step 1: Replace `_VBPL_INDEX_FIELDS` constant**

Replace lines 186-198 with:

```python
_PHAPDIEN_INDEX_FIELDS = (
    "article_anchor",
    "article_title",
    "chapter_title",
    "subject_title",
    "topic_title",
    "source_url",
    "scraped_at",
)
```

Also update the reference at line 446 from `_VBPL_INDEX_FIELDS` to `_PHAPDIEN_INDEX_FIELDS`.

- [ ] **Step 2: Run qdrant test suite, verify still passes**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_qdrant_service.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/services/qdrant_service.py
git commit -m "feat(qdrant): index only phapdien-moj filterable fields"
```

---

## Task 8: Strip dead chunking/HTML code from `qdrant_service.py`

**Files:**
- Modify: `backend/services/qdrant_service.py` (top section: lines 1-499)

- [ ] **Step 1: Confirm `split_legal_chunks`, `HTMLLegalParser`, `clean_html_text`, `split_document_chunks`, `detect_doc_format` have no remaining callers**

Run: `cd backend && grep -rn "split_legal_chunks\|HTMLLegalParser\|clean_html_text\|split_document_chunks\|detect_doc_format\|build_vbpl_source_url" . 2>&1 | grep -v __pycache__`
Expected: only the definitions in `qdrant_service.py` remain (and `scripts/ingest_phapdien.py` for `split_legal_chunks` + `clean_html_text` — that's the legacy th1nhng0 path, will be cleaned in a follow-up).

If the legacy `scripts/ingest_phapdien.py` still imports them, leave them in `qdrant_service.py` for now. Mark with a `# legacy th1nhng0 path` comment.

- [ ] **Step 2: Add `# legacy th1nhng0 path` comment above the chunking block**

In `qdrant_service.py`, add a comment above line 36 (the `class HTMLLegalParser`):

```python
# ---------------------------------------------------------------------------
# Legacy th1nhng0 path: kept for scripts/ingest_phapdien.py. Will be removed
# in a follow-up when the th1nhng0 collection is also re-ingested via the
# passthrough pipeline. Do not use for new code.
# ---------------------------------------------------------------------------
```

- [ ] **Step 3: Verify no test references these symbols**

Run: `cd backend && grep -rn "split_legal_chunks\|HTMLLegalParser\|clean_html_text\|split_document_chunks\|detect_doc_format" tests/ 2>&1 | grep -v __pycache__`
Expected: many matches in `test_qdrant_service.py` — these tests are now testing dead code. Delete them in the next task.

- [ ] **Step 4: No code change here, just commit the comment marker**

```bash
git add backend/services/qdrant_service.py
git commit -m "docs(qdrant): mark chunking/HTML code as legacy th1nhng0 path"
```

---

## Task 9: Clean up `test_qdrant_service.py` — delete dead-code tests

**Files:**
- Modify: `backend/tests/services/test_qdrant_service.py`

- [ ] **Step 1: Delete tests covering removed symbols**

Delete the following test functions (they test code that's marked legacy and not used by phapdien-moj path):

- `test_clean_html_text_strips_tags_and_keeps_vietnamese_text` (line 114-119)
- `test_split_document_chunks_respects_max_length` (line 122-135)
- `test_split_legal_chunks_preserves_chapter_and_article_labels` (line 304-326)
- `test_split_legal_chunks_sub_splits_only_within_one_article` (line 329-353)
- `test_split_legal_chunks_falls_back_to_paragraph_mode_for_decisions` (line 356-375)
- `test_ingest_articles_stores_legal_structure_metadata_on_payload` (line 378-412) — tests `chunk_level`/`chapter_label`/`article_label`/`total_chunks` in payload, all removed
- `test_html_parser_extracts_headings` (line 605-622)
- `test_html_parser_extracts_paragraphs` (line 625-628)
- `test_html_parser_preserves_semantic_structure` (line 631-645)
- `test_split_legal_chunks_respects_khoan` (line 648-661)
- `test_split_legal_chunks_long_article` (line 664-672)
- `test_split_legal_chunks_preserves_metadata` (line 675-684)
- `test_split_legal_chunks_handles_decision_format` (line 687-694)

Keep and update:
- `test_embed_texts_calls_ollama_with_configured_model` — keep
- `test_embed_texts_returns_empty_when_no_inputs` — keep
- `test_embed_texts_raises_when_ollama_returns_no_embedding` — keep
- `test_embed_texts_retries_with_ascii_normalized_text_after_500` — keep
- `test_detect_doc_format_returns_law_for_repeated_dieu_markers` — delete (covers removed `detect_doc_format`? actually `detect_doc_format` is in legacy section, see Task 8.1; if not used elsewhere, delete)
- `test_detect_doc_format_returns_decision_for_decision_style_text` — delete (same)
- `test_search_legal_context_returns_vbpl_fields` — replace with 5-field shape (Task 4 step 5 covers it)
- `test_search_with_loai_van_ban_filter_passes_filter_to_qdrant` — delete (no filter is built; `search_legal_context` ignores `filters` arg in the new implementation; we'll re-add filtering in a follow-up if needed)
- `test_ingest_articles_stores_vbpl_chunk_payload` — delete (old shape)
- `test_ingest_articles_calls_embed_with_documents` — keep but update input to use new schema
- `test_ingest_articles_stores_relationships_in_payload` — delete (no relationships)
- `test_ingest_articles_stores_empty_relationships_when_missing` — delete
- `test_search_legal_context_returns_relationships` — delete
- `test_search_legal_context_returns_empty_relationships_when_missing` — delete
- `test_search_legal_context_returns_legal_chunk_metadata_fields` — delete (chunk metadata gone)
- `test_ingest_articles_preserves_all_phapdien_moj_fields` — added in Task 2
- `test_ingest_articles_id_is_deterministic_uuid5` — added in Task 2
- `test_search_legal_context_returns_only_consumed_fields` — added in Task 4

- [ ] **Step 2: Update `test_ingest_articles_calls_embed_with_documents`**

Replace its body (lines 246-274) with:

```python
def test_ingest_articles_calls_embed_with_documents() -> None:
    from services.qdrant_service import ingest_articles

    row = {
        "id": "abc",
        "article_anchor": "#abc",
        "article_title": "Điều 1",
        "content_text": "Quy định về ly hôn",
        "source_url": "https://phapdien.moj.gov.vn/x",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([row])

    args, kwargs = mock_embed.call_args
    texts = args[0] if args else kwargs.get("texts")
    assert texts == ["Quy định về ly hôn"]
```

- [ ] **Step 3: Run full qdrant test suite**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_qdrant_service.py -v`
Expected: PASS, ~6-8 tests instead of ~25.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/services/test_qdrant_service.py
git commit -m "test(qdrant): remove tests for dead chunking/HTML/relationships code"
```

---

## Task 10: Update `chat_service` for new field shape (no more `doc_id` fallback)

**Files:**
- Modify: `backend/services/chat_service.py:72, 75, 78, 126, 128`

- [ ] **Step 1: Replace `c.get("id") or c.get("doc_id")` with `c.get("id")` everywhere**

Three call sites:

- Line 72 (`_multi_query_retrieve`): `cid = chunk.get("id")`
- Line 75: `if cid not in seen or chunk.get("score", 0) > seen[cid].get("score", 0):` — unchanged, just verify `cid` is now always from `id`
- Line 78: `merged.sort(key=lambda c: c.get("score", 0), reverse=True)` — unchanged

Run: `cd backend && grep -n "doc_id" services/chat_service.py`
Expected: no matches after the edit (Task 6 already removed lines 126, 128).

- [ ] **Step 2: Run chat_service tests**

Run: `cd backend && ./.venv/bin/python -m pytest tests/services/test_chat_service.py tests/test_chat_service.py 2>&1 | tail -20`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/services/chat_service.py
git commit -m "refactor(chat): use only id for context dedupe, no more doc_id fallback"
```

---

## Task 11: Rewrite `ingest_phapdien_moj.py` to use 1-row-1-record passthrough

**Files:**
- Modify: `scripts/ingest_phapdien_moj.py:1-5, 17-29, 66-116, 179-200`

- [ ] **Step 1: Update top-of-file docstring**

Replace lines 1-5 with:

```python
#!/usr/bin/env python3
"""
Ingestion script for tmquan/phapdien-moj-gov-vn dataset.
Loads articles directly (already cleaned, one article per row) and upserts
each row to Qdrant Cloud as a single point — no chunking.
"""
```

- [ ] **Step 2: Update imports**

Replace the `core.config` import block (lines 17-23) with:

```python
from core.config import (  # noqa: E402
    INGEST_BATCH_SIZE,
    PHAPDIEN_MAX_CONTENT_CHARS,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)
```

Replace the `qdrant_service` import block (lines 24-29) with:

```python
from services.qdrant_service import (  # noqa: E402
    ensure_collection_exists,
    get_qdrant_client,
    ingest_articles,
)
```

- [ ] **Step 3: Replace `build_chunk_records` with `build_point_record`**

Replace lines 66-116 with:

```python
def build_point_record(row: dict, row_index: int) -> dict | None:
    """Build a single Qdrant-ready record from one phapdien-moj dataset row.

    Returns None when the row should be skipped (empty content, oversized
    content beyond embedder capacity, or missing anchor).
    """
    content_text = (row.get("content_text") or "").strip()
    if not content_text:
        return None

    if len(content_text) > PHAPDIEN_MAX_CONTENT_CHARS:
        # bge-m3 max ≈ 8K tokens (~20K Vietnamese chars); the top 0.5% of
        # rows in this dataset are clearly corrupted/legal-compilation dumps
        # (8MB, 530K, 447K chars) and would exceed the embedder's window.
        print(
            f"  [skip] row {row_index} anchor={row.get('article_anchor')!r} "
            f"content too long ({len(content_text)} chars > {PHAPDIEN_MAX_CONTENT_CHARS})"
        )
        return None

    article_anchor = row.get("article_anchor")
    if not article_anchor:
        print(f"  [skip] row {row_index} missing article_anchor")
        return None

    return {
        "id": str(article_anchor).lstrip("#"),
        "article_anchor": article_anchor,
        "article_title": row.get("article_title", "") or "",
        "content_text": content_text,
        "content_char_len": int(row.get("content_char_len") or len(content_text)),
        "content_word_count": int(row.get("content_word_count") or 0),
        "chapter_title": row.get("chapter_title", "") or "",
        "subject_id": row.get("subject_id", "") or "",
        "subject_number": int(row.get("subject_number") or 0),
        "subject_title": row.get("subject_title", "") or "",
        "topic_id": row.get("topic_id", "") or "",
        "topic_number": int(row.get("topic_number") or 0),
        "topic_title": row.get("topic_title", "") or "",
        "source_note_text": row.get("source_note_text", "") or "",
        "source_links": list(row.get("source_links") or []),
        "related_note_text": row.get("related_note_text", "") or "",
        "source_url": row.get("source_url", "") or "",
        "scraped_at": row.get("scraped_at", "") or "",
    }
```

- [ ] **Step 4: Update the `main()` loop**

Replace the loop in `main()` (lines 179-200) with:

```python
    for i in range(start_index, end_index + 1):
        row = dataset[i]
        record = build_point_record(row, i)
        if record is None:
            continue
        pending.append(record)
        processed += 1

        should_flush = len(pending) >= batch_size
        reached_limit = args.limit is not None and processed >= args.limit
        at_end = i == end_index
        if not should_flush and not reached_limit and not at_end:
            continue

        if pending:
            print(f"\nUpserting {len(pending)} points after index {i}")
            ingest_articles(pending, batch_size=batch_size)
            last_id = pending[-1]["id"]
            save_checkpoint(i, last_id, checkpoint_path=checkpoint_path, worker_id=args.worker_id)
            print(f"  Checkpoint saved: index {i}, last point {last_id}")
            pending = []

        if reached_limit:
            break
```

- [ ] **Step 5: Smoke test on first 50 rows**

Run: `cd /home/khoa/Company/VietNamLaw && QDRANT_COLLECTION_NAME=legal_articles_test ./.venv/bin/python scripts/ingest_phapdien_moj.py --limit 50 --reset-checkpoint --start-index 0`
Expected: prints 1-2 "skip" messages for empty content; otherwise upserts ~48 points. Qdrant test collection will have ~48 points.

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_phapdien_moj.py
git commit -m "feat(ingest): one phapdien-moj row = one Qdrant point, no chunking"
```

---

## Task 12: Run full test suite end-to-end

**Files:** none

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && ./.venv/bin/python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Manual integration test**

Run: `cd /home/khoa/Company/VietNamLaw && QDRANT_COLLECTION_NAME=legal_articles_test ./.venv/bin/python -c "
from services.qdrant_service import search_legal_context, get_qdrant_client
client = get_qdrant_client()
info = client.get_collection('legal_articles_test')
print(f'points: {info.points_count}')
results = search_legal_context('điều kiện ly hôn đơn phương', top_k=3)
for r in results:
    print(f'  score={r[\"score\"]:.3f} title={r[\"title\"]!r} url={r[\"source_url\"]!r}')
    print(f'    content[:120]={r[\"content_text\"][:120]!r}')
    assert set(r.keys()) == {'id', 'content_text', 'title', 'source_url', 'score'}
print('return shape OK: 5 fields only')
" 2>&1 | head -20`
Expected: prints 3 results; last line says "return shape OK: 5 fields only".

- [ ] **Step 3: Drop test collection**

Run: `cd /home/khoa/Company/VietNamLaw/backend && ./.venv/bin/python -c "
from services.qdrant_service import get_qdrant_client
client = get_qdrant_client()
client.delete_collection('legal_articles_test')
print('dropped test collection')
"`

- [ ] **Step 4: Commit (no code change, just marker)**

```bash
git commit --allow-empty -m "test: full suite passes, integration smoke OK"
```

---

## Task 13: Update `docs/qdrant-setup.md`

**Files:**
- Modify: `docs/qdrant-setup.md:21-30`

- [ ] **Step 1: Update the indexed-fields list**

Replace lines 21-30 with:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/qdrant-setup.md
git commit -m "docs(qdrant): document phapdien-moj indexed fields"
```

---

## Task 14: Final re-ingestion (manual, post-merge)

**Files:** none (operational step, not a code change)

- [ ] **Step 1: Drop the old chunked collection**

Run:

```bash
cd /home/khoa/Company/VietNamLaw/backend
./.venv/bin/python -c "
from services.qdrant_service import get_qdrant_client
import os
c = get_qdrant_client()
c.delete_collection(os.environ['QDRANT_COLLECTION_NAME'])
print('dropped old chunked collection')
"
```

- [ ] **Step 2: Run full re-ingestion**

Run: `cd /home/khoa/Company/VietNamLaw && ./.venv/bin/python scripts/ingest_phapdien_moj.py --reset-checkpoint`
Expected: 64,464 - 406 empty - ~336 oversized ≈ 63,720 points. Logs the number of skipped rows at the end.

- [ ] **Step 3: Verify collection size and payload shape**

Run:

```bash
cd /home/khoa/Company/VietNamLaw/backend
./.venv/bin/python -c "
from services.qdrant_service import get_qdrant_client
c = get_qdrant_client()
info = c.get_collection('legal_articles')
print(f'points: {info.points_count}')
points, _ = c.scroll(collection_name='legal_articles', limit=1, with_payload=True, with_vectors=False)
p = points[0]
print(f'fields: {sorted(p.payload.keys())}')
"
```

Expected: `points: ~63720`; `fields` includes the 17 phapdien-moj keys and **no** `chunk_index`, `total_chunks`, `chunk_level`, `chapter_label`, `article_label`, `relationships`, `doc_id`, `loai_van_ban`, `co_quan_ban_hanh`, `tinh_trang_hieu_luc`, `linh_vuc`, `nganh`, `so_ky_hieu`, `title`.

- [ ] **Step 4: Rebuild BM25 index**

Run: `cd /home/khoa/Company/VietNamLaw/backend && ./.venv/bin/python scripts/build_bm25_index.py`
Expected: builds new pickle, logs `Built BM25 index with 63720 documents` (≈).

- [ ] **Step 5: Smoke test through chat endpoint**

Run: `cd /home/khoa/Company/VietNamLaw && ./.venv/bin/python -c "
from services.chat_service import send_chat_message
# Mock the DB call
class FakeDB: pass
# This is just a sanity test that the imports still resolve
print('chat_service imports OK; crossref_walker no longer in module list')
import services.chat_service as cs
assert not hasattr(cs, 'walk_relationships'), 'walk_relationships should be gone'
print('OK')
"`

---

## Self-Review

- **Spec coverage:** all 17 fields preserved (Task 3 + Task 11). Empty/oversized handling (Task 11). Collection schema update (Task 7). Return shape trimmed to 5 fields (Task 4 + Task 5). Crossref deleted (Task 6). Legacy fallbacks deleted (Task 9). Verification (Task 12). Re-ingestion (Task 14). ✓
- **Placeholder scan:** every code block contains real code. ✓
- **Type consistency:** `point_id` derives from `article_anchor.lstrip('#')` in both `ingest_articles` (Task 3) and `build_point_record` (Task 11 step 3). The `id` field on the record matches the string fed to `uuid5`. ✓
- **No dangling references:** Task 6 deletes the file; Task 6 step 4 greps to verify; Task 10 cleans `chat_service` references. ✓
- **Test count drops** from ~25 qdrant tests to ~6-8; from ~10 bm25 to ~3; crossref test file deleted (3 tests). Net: -30 tests, all of which were testing dead code. ✓
