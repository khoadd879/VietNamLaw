# Store Full Dataset Row as Qdrant Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual 14-field mapping in `qdrant_service._embed_and_build` with a passthrough that stores the entire dataset row (all 17 HF fields) as the Qdrant payload metadata, plus a small parser to populate the `relationships[]` list from `related_note_text` so crossref_walker actually works.

**Architecture:** Two changes — (1) `qdrant_service.ingest_articles` now takes a `payload: dict` argument and stores it verbatim instead of cherry-picking fields; (2) the ingest script builds that payload by spreading the raw HF row (with a few computed fields like `id`, `doc_id`, `chunk_index` overlaid) and parsing `related_note_text` into a `relationships[]` list of article titles. Existing callers (`citation_verifier`, `bm25_index`, `crossref_walker`) keep reading the same payload keys they already use — backwards compatible because we preserve the field names they expect.

**Tech Stack:** Python 3.11+, Qdrant client, HuggingFace `datasets` library, pytest.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `backend/services/qdrant_service.py` | Modify `ingest_articles` signature + body | New `payload` arg stored verbatim in PointStruct |
| `scripts/ingest_phapdien_moj.py` | Modify `build_chunk_records` | Build full-row payload (spread `row` + computed fields + parsed `relationships`) |
| `backend/services/related_note_parser.py` | Create | Parse `related_note_text` → list of article references |
| `backend/tests/services/test_related_note_parser.py` | Create | Unit tests for the parser |
| `backend/tests/services/test_qdrant_service.py` | Modify | Add test for new `payload` arg passthrough |

---

### Task 1: Write failing tests for `related_note_parser`

**Files:**
- Create: `backend/tests/services/test_related_note_parser.py`

- [ ] **Step 1: Write the failing tests**

```python
from services.related_note_parser import parse_related_article_titles


def test_parse_single_article() -> None:
    note = "(Điều này có nội dung liên quan đến Điều 1.1.LQ.1. Phạm vi điều chỉnh)"
    assert parse_related_article_titles(note) == ["Điều 1.1.LQ.1. Phạm vi điều chỉnh"]


def test_parse_multiple_articles_separated_by_semicolons() -> None:
    note = (
        "(Điều này có nội dung liên quan đến "
        "Điều 1.12.LQ.11. Biện pháp cảnh vệ ; "
        "Điều 1.11.LQ.1. Phạm vi điều chỉnh ; "
        "Điều 1.6.LQ.16. Nhiệm vụ của Công an nhân dân )"
    )
    result = parse_related_article_titles(note)
    assert result == [
        "Điều 1.12.LQ.11. Biện pháp cảnh vệ",
        "Điều 1.11.LQ.1. Phạm vi điều chỉnh",
        "Điều 1.6.LQ.16. Nhiệm vụ của Công an nhân dân",
    ]


def test_parse_empty_string_returns_empty_list() -> None:
    assert parse_related_article_titles("") == []


def test_parse_none_returns_empty_list() -> None:
    assert parse_related_article_titles(None) == []


def test_parse_unrelated_text_returns_empty_list() -> None:
    # Random text with no "Điều X.Y." pattern
    assert parse_related_article_titles("some random text without articles") == []


def test_parse_handles_extra_whitespace() -> None:
    note = "(Điều này có nội dung liên quan đến    Điều 5.1.LQ.2.    Quy định chung   )"
    assert parse_related_article_titles(note) == ["Điều 5.1.LQ.2. Quy định chung"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/pytest tests/services/test_related_note_parser.py -v
```

Expected: ImportError or ModuleNotFoundError (parser doesn't exist yet).

- [ ] **Step 3: Implement `related_note_parser.py`**

Create `backend/services/related_note_parser.py`:

```python
"""Parse the related_note_text field from the phapdien dataset into a list of related article titles.

The dataset stores cross-references as a single string like:
  "(Điều này có nội dung liên quan đến Điều 1.12.LQ.11. Biện pháp cảnh vệ ; Điều 1.11.LQ.1. ...)"

We split on `;` then strip each piece down to the "Điều X.Y.<type>.N. <title>" form.
The result feeds the Qdrant payload's `relationships[]` field, which
crossref_walker.py reads to fetch related chunks.
"""
import re
from typing import Any

# Match "Điều <digits>.<digits>.<TYPE>.<digits>." followed by an optional title.
# Stops at the next ";" or end of string.
_ARTICLE_TILE_RE = re.compile(
    r"Điều\s+\d+\.\d+\.[A-ZĐ]+\.\d+\.[^;]*",
    re.UNICODE,
)


def parse_related_article_titles(related_note_text: Any) -> list[str]:
    """Extract a clean list of related article titles from the dataset's related_note_text.

    Returns [] for empty/None input or text with no Điều patterns.
    """
    if not related_note_text:
        return []
    matches = _ARTICLE_TILE_RE.findall(related_note_text)
    return [m.strip() for m in matches if m.strip()]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/pytest tests/services/test_related_note_parser.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/khoa/Company/VietNamLaw && git add backend/services/related_note_parser.py backend/tests/services/test_related_note_parser.py && git commit -m "feat(ingest): add related_note parser for dataset cross-references"
```

---

### Task 2: Modify `qdrant_service.ingest_articles` to accept a `payload` dict

**Files:**
- Modify: `backend/services/qdrant_service.py:558-589`
- Modify: `backend/tests/services/test_qdrant_service.py:213-244`

- [ ] **Step 1: Update the existing test in `test_qdrant_service.py` to pass the new `payload` arg**

In `test_ingest_articles_stores_vbpl_chunk_payload` (around line 213), change the call to pass an explicit `payload` dict and assert on those exact keys:

```python
def test_ingest_articles_stores_payload_verbatim() -> None:
    from services.qdrant_service import ingest_articles

    payload = {
        "content_text": "Khoản 1. Quy định thử nghiệm.",
        "article_title": "Điều 1. Phạm vi áp dụng",
        "chapter_title": "Chương I - Quy định chung",
        "source_note_text": "(Điều 1 Luật số 32/2004/QH11 ngày 03/12/2004)",
        "related_note_text": "(liên quan đến Điều 2.1.LQ.1. Quy định bổ sung)",
        "source_url": "https://vbpl.vn/.../ItemID=123",
        "relationships": ["Điều 2.1.LQ.1. Quy định bổ sung"],
    }

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "content_text": payload["content_text"],
        "payload": payload,
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point.payload == payload  # exact passthrough
    assert point.id == point.id  # uuid5 deterministic
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/pytest tests/services/test_qdrant_service.py::test_ingest_articles_stores_payload_verbatim -v
```

Expected: FAIL — either ImportError if old test name, or assertion error when comparing payload (old code cherry-picks 14 keys).

- [ ] **Step 3: Replace `_embed_and_build` and the `ingest_articles` signature in `qdrant_service.py`**

Replace lines 558-589 (the whole `ingest_articles` function body) with:

```python
def ingest_articles(articles: list[dict], batch_size: int | None = None) -> None:
    """Embed and upsert articles to Qdrant.

    Each `article` dict MUST have:
      - `id` (str): stable identifier
      - `content_text` (str): text to embed
      - `payload` (dict): full metadata to store alongside the vector

    The payload is stored verbatim — no field cherry-picking — so the
    ingest script can persist the entire HF dataset row plus any
    computed fields (id, doc_id, chunk_index, relationships).
    """
    if batch_size is None:
        batch_size = INGEST_BATCH_SIZE
    client = get_qdrant_client()
    workers = INGEST_CONCURRENT_WORKERS

    def _embed_and_build(article: dict) -> PointStruct:
        vector = embed_texts([article["content_text"]], task_type="RETRIEVAL_DOCUMENT")[0]
        raw_id = str(article["id"])
        point_id = str(uuid5(NAMESPACE_URL, f"vbpl:{raw_id}"))
        return PointStruct(
            id=point_id,
            vector=vector,
            payload=article["payload"],
        )

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

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/pytest tests/services/test_qdrant_service.py::test_ingest_articles_stores_payload_verbatim -v
```

Expected: PASS.

- [ ] **Step 5: Run the full qdrant test file to make sure nothing else broke**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/pytest tests/services/test_qdrant_service.py -v
```

Expected: All tests pass (the new one + any existing ones that don't depend on the cherry-picked fields).

- [ ] **Step 6: Commit**

```bash
cd /home/khoa/Company/VietNamLaw && git add backend/services/qdrant_service.py backend/tests/services/test_qdrant_service.py && git commit -m "refactor(qdrant): store payload verbatim instead of cherry-picking fields"
```

---

### Task 3: Update `scripts/ingest_phapdien_moj.py` to build the full-row payload

**Files:**
- Modify: `scripts/ingest_phapdien_moj.py:66-116` (`build_chunk_records`)

- [ ] **Step 1: Update the imports**

At the top of the file, add the new import:

```python
from services.related_note_parser import parse_related_article_titles
```

- [ ] **Step 2: Replace `build_chunk_records` with the new full-row implementation**

Replace lines 66-116 with:

```python
def build_chunk_records(row: dict, row_index: int) -> list[dict]:
    """Build article dicts for ingest_articles from one HF dataset row.

    For each chunk, we build a `payload` dict that contains:
      - All 17 fields from the HF row (spread verbatim)
      - Computed fields: id, doc_id, chunk_index, total_chunks
      - Parsed `relationships` list extracted from `related_note_text`
    """
    content_text = (row.get("content_text") or "").strip()
    if not content_text:
        return []

    # Skip cực lớn (>100K chars) - thường là bảng dữ liệu, không phù hợp embed
    if len(content_text) > 100000:
        return []

    article_anchor = row.get("article_anchor") or f"article_{row_index}"
    doc_id = str(article_anchor).lstrip("#") or f"article_{row_index}"

    if len(content_text) <= LEGAL_CHUNK_MAX_CHARS:
        chunks = [{
            "content_text": content_text,
            "chapter_label": row.get("chapter_title"),
            "article_label": row.get("article_title"),
            "chunk_level": "article",
        }]
    else:
        chunks = split_legal_chunks(
            content_text,
            max_chars=LEGAL_CHUNK_MAX_CHARS,
            article_threshold=LEGAL_ARTICLE_CHAPTER_THRESHOLD,
        )
        chunks = [c for c in chunks if str(c.get("content_text", "") or "").strip()]
        if len(chunks) > 30:
            chunks = chunks[:30]

    total_chunks = len(chunks)
    relationships = parse_related_article_titles(row.get("related_note_text", ""))

    records = []
    for chunk_index, chunk in enumerate(chunks):
        # Start with the full row spread, then overlay chunk-specific + computed fields
        payload = {
            **row,  # all 17 HF fields (subject_id, topic_title, source_note_text, etc.)
            # Chunk-level overrides
            "content_text": str(chunk.get("content_text", "") or ""),
            "chapter_label": chunk.get("chapter_label") or row.get("chapter_title"),
            "article_label": chunk.get("article_label") or row.get("article_title"),
            "chunk_level": chunk.get("chunk_level", "article"),
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "doc_id": doc_id,
            # Parsed cross-references for crossref_walker
            "relationships": relationships,
        }
        records.append({
            "id": f"{doc_id}:{chunk_index}",
            "content_text": payload["content_text"],
            "payload": payload,
        })
    return records
```

- [ ] **Step 3: Run the parser tests once more to confirm the import is wired**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/pytest tests/services/test_related_note_parser.py -v
```

Expected: 6 passed.

- [ ] **Step 4: Smoke-test the script with `--limit 1` to confirm it builds records without crashing**

```bash
cd /home/khoa/Company/VietNamLaw && python scripts/ingest_phapdien_moj.py --limit 1 --start-index 0
```

Expected: prints "Done! Articles processed: 1" (or skips the row if it's >100K chars). If it errors, check that the import path is correct.

- [ ] **Step 5: Commit**

```bash
cd /home/khoa/Company/VietNamLaw && git add scripts/ingest_phapdien_moj.py && git commit -m "refactor(ingest): spread full HF row into Qdrant payload, parse relationships"
```

---

### Task 4: Re-run ingest and verify Qdrant has the new fields

**Files:** none (manual verification)

- [ ] **Step 1: Run the full re-ingest**

```bash
cd /home/khoa/Company/VietNamLaw && python scripts/ingest_phapdien_moj.py --reset-checkpoint
```

Expected: Runs for 5-15 min, prints "Done! Articles processed: N" at the end. If it crashes, check the error — most likely cause is HF rate-limiting (set `HF_TOKEN` env var) or OOM (lower `INGEST_BATCH_SIZE`).

- [ ] **Step 2: Spot-check Qdrant to confirm new fields are stored**

```bash
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/python -c "
from services.qdrant_service import get_qdrant_client, QDRANT_COLLECTION_NAME
client = get_qdrant_client()
points, _ = client.scroll(collection_name=QDRANT_COLLECTION_NAME, limit=3, with_payload=True, with_vectors=False)
for p in points:
    pl = p.payload
    print('---')
    print('  article_label :', pl.get('article_label'))
    print('  source_note_text:', bool(pl.get('source_note_text')))
    print('  related_note_text:', bool(pl.get('related_note_text')))
    print('  subject_title:', pl.get('subject_title'))
    print('  topic_title:', pl.get('topic_title'))
    print('  relationships:', pl.get('relationships'))
"
```

Expected: All `bool(...)` checks return `True`, and `relationships` is a non-empty list for most points.

- [ ] **Step 3: Rebuild BM25 index**

Restart the backend — it auto-builds the BM25 index on startup if missing:

```bash
# Stop backend if running, then:
cd /home/khoa/Company/VietNamLaw/backend && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Watch the startup logs for "BM25 index built with N docs" — should match the dataset size.

- [ ] **Step 4: Commit any data checkpoint files (optional)**

The script saves `data/.ingest_phapdien_moj.json` — add it if you want the resume checkpoint tracked.

```bash
cd /home/khoa/Company/VietNamLaw && git add data/.ingest_phapdien_moj.json && git commit -m "chore: save ingest checkpoint after full re-run" || true
```

(This is optional — checkpoint is for resume, not for code review.)

---

### Task 5: Update spec to reflect the simpler approach

**Files:**
- Modify: `docs/superpowers/specs/2026-06-01-citation-format-response-depth-design.md`

- [ ] **Step 1: Replace Step 1 of "Approach" with the new approach**

Find the section starting with `### Step 1 — Fix \`ingest_articles()\` to read existing article dict fields` and replace it (down to `### Step 2 — Re-run the existing ingest script`) with:

```markdown
### Step 1 — Store the full HF dataset row as the Qdrant payload

Replace `_embed_and_build()` so it stores a `payload: dict` verbatim, instead of cherry-picking 14 specific fields. The ingest script then spreads the entire HF row (all 17 fields) into the payload, plus computes `id`/`doc_id`/`chunk_index`/`total_chunks` and a parsed `relationships[]` list.

**Why this is better than the original spec:**
- Future dataset fields are picked up automatically (no need to update `qdrant_service.py` again)
- No more dropped metadata — every field is queryable
- Smaller diff in the library code

**Implementation in 3 places:**
1. `backend/services/qdrant_service.py:558-589` — `ingest_articles()` takes `article["payload"]` and stores it directly
2. `backend/services/related_note_parser.py` (new) — parses `related_note_text` into `relationships[]`
3. `scripts/ingest_phapdien_moj.py:66-116` — `build_chunk_records()` spreads `**row` and overlays computed fields

**Backwards compatibility:** the same payload keys (`content_text`, `article_label`, `chapter_label`, `source_url`, `relationships`) still exist, so `citation_verifier.py`, `bm25_index.py`, `crossref_walker.py`, and the legal-citation-chip keep working without changes.
```

- [ ] **Step 2: Commit**

```bash
cd /home/khoa/Company/VietNamLaw && git add docs/superpowers/specs/2026-06-01-citation-format-response-depth-design.md && git commit -m "docs(spec): align with full-row payload approach"
```

---

## Self-Review

- **Spec coverage:** Plan covers 5 tasks — parser, payload passthrough, script update, manual re-ingest verification, spec alignment. The follow-up enricher + frontend changes from the original spec are intentionally **out of scope** here; they belong to a separate plan (citation-format-display.md) that depends on this one landing first.
- **Placeholders:** None — every step shows full code.
- **Type consistency:** `article["payload"]` is referenced consistently in Tasks 2, 3, 4. `parse_related_article_titles` is the same function used in test (Task 1) and script (Task 3).
- **Out-of-scope follow-up:** After this plan lands, the original `citation_enricher` + frontend changes still need a separate plan. That's deliberate — keeps each plan shippable independently.
