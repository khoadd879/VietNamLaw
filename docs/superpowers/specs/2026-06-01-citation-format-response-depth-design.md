# Design: Citation Format & Response Depth

**Date:** 2026-06-01
**Status:** Approved (Approach A + re-ingest)
**Author:** Claude + Khoa

## Context

User feedback (post-Sprint 3): citations show up as raw URLs (`https://phapdien.moj.gov.vn/...`) instead of legal-reference style ("Điều 51 Luật Hôn nhân và gia đình 2014"). Responses also feel thin — short 1-2 paragraph analyses without concrete dẫn chiếu.

### Investigation findings (2026-06-01)

Sampled 5 points from Qdrant + 1 record from HuggingFace dataset `tmquan/phapdien-moj-gov-vn/articles`:

**Dataset fields actually present** (raw `articles` config):
- `article_title`: `"Điều 1.1.LQ.1. Phạm vi điều chỉnh"` (chapter.article.topic internal code, not user-friendly)
- `chapter_title`: `"Chương I - NHỮNG QUY ĐỊNH CHUNG"`
- `source_note_text`: `"(Điều 1 Luật số 32/2004/QH11 An ninh Quốc gia ngày 03/12/2004 của Quốc hội...)"` ← **gold: complete law reference with name + number + year**
- `source_links`: list of `{text, href}` dicts
- `source_url`: phapdien.moj.gov.vn URL
- `topic_title`, `subject_title`

**Qdrant payload currently stores** (verified by `client.scroll`):
- ✅ `article_label` (= `article_title` from dataset, internal-coded)
- ✅ `chapter_label` (= `chapter_title`)
- ✅ `source_url`
- ❌ `source_note_text` (NOT stored)
- ❌ `source_links` (NOT stored)
- ❌ `article_title`, `chapter_title` (stored under different names only)

**Conclusion:** the data we need is in the source dataset but was filtered out during the original ingest. A re-ingest that preserves `source_note_text` is the root-cause fix — every other path (heuristic parsing, fallback labels) is a workaround that produces ugly output.

## Goals

1. Citations render as proper legal references: `Điều X · Luật số NN/NN/QHYY Tên Luật` (with Khoản/Điểm when present), still click-through to the source URL
2. Responses are moderately longer and more structured — explicit dẫn chiếu điều luật cụ thể, phương án có bước hành động
3. Existing UX (chips, expand-to-link) preserved — just better content
4. Cite directly from `source_note_text` instead of regex-parsing (more robust)

## Non-goals

- Re-architecting the retrieval pipeline
- Caching the enriched citation labels
- Adding new structured fields beyond what the LLM schema already has
- Full Vietnamese typography / diacritics cleanup (separate concern)

## Approach: Re-ingest + backend enrich + tighten prompt

### Step 1 — Re-ingest Qdrant with new payload fields

Modify `ingest_articles()` in `backend/services/qdrant_service.py` to read these additional fields from the article dict and store them in each point's payload:

| New payload field | Source from dataset | Use in enricher |
|---|---|---|
| `source_note_text` | `source_note_text` | **Primary**: full legal reference like `(Điều 1 Luật số 32/2004/QH11 An ninh Quốc gia ngày 03/12/2004 của Quốc hội...)` |
| `article_title_full` | `article_title` | "Điều 1.1.LQ.1. Phạm vi điều chỉnh" — long internal form (kept for debugging) |
| `chapter_title_full` | `chapter_title` | "Chương I - NHỮNG QUY ĐỊNH CHUNG" |
| `source_links` | `source_links` | list of `{text, href}` — alternative URLs |

`article_label` and `chapter_label` keep their current short form (used for matching, not display). Add the new fields alongside.

**Re-ingest mechanics:**
- One-off script: `backend/scripts/reingest_with_citation_fields.py`
- Reads from same HF dataset config (`articles`, split `train`)
- Calls existing `ingest_articles()` with payload updates
- **Destructive** — wipes `legal_articles` collection first, re-embeds everything
- Run takes ~5-15 min for the full dataset; can be done overnight or while dev is paused
- BM25 index also needs rebuild after re-ingest (existing helper handles this)

### Step 2 — Backend enricher uses `source_note_text` (no regex!)

New module: `backend/services/citation_enricher.py` (~50 lines, smaller than original spec because the heavy lifting is now data, not parsing).

For each string in `structured.trich_dan_nguon`:
1. Parse "Điều X" / "Khoản Y" / "Điểm Z" from the LLM citation
2. Find matching context by article number (in `article_label` or `content_text`)
3. If matched, get `source_note_text` from that context — this is the full legal reference
4. Build display label: combine parsed parts + law reference from `source_note_text`

Example output:
- LLM says: `"Khoản 2 Điều 51"`
- Matched chunk has `source_note_text = "(Điều 51 Luật Hôn nhân và Gia đình 2014)"`
- Display: `"Khoản 2 · Điều 51 · Luật Hôn nhân và Gia đình 2014"`

If no `source_note_text` available → fall back to raw citation string (no crash).

### Step 3 — Synthesizer prompt edit

Edit the synthesizer prompt (location TBD, see open questions) to:
- Forbid URL in `trich_dan_nguon` (instruct LLM to write "Điều X" form)
- Add length guidance per field (phan_tich_phap_ly: 2-4 đoạn 80-150 từ; phuong_an: 1-3 câu có bước hành động; rui_ro: 1-2 câu nêu hậu quả pháp lý; cau_hoi: ngắn gọn tập trung facts còn thiếu)

### Step 4 — Frontend render

- `frontend/lib/api.ts`: add `trich_dan_nguon_label?: string[]` to `LawyerSection`
- `frontend/components/chat/legal-citation-chip.tsx`: add optional `label` prop, prefer it over regex-parsed label

## Data flow

```
HuggingFace articles row
   ↓
[ingest_articles]  ──stores──>  Qdrant payload: {article_label, source_note_text, source_url, ...}
                                              ↓
User query  ──retrieve──>  contexts[] (each with source_note_text)
                                              ↓
LLM (Groq)  ──returns──>  structured.trich_dan_nguon: ["Khoản 2 Điều 51", ...]
                                              ↓
verify_citations()  ──drops unverifiable──>  filtered list
                                              ↓
enrich_citations(structured, contexts)  ──joins on article──>  structured.trich_dan_nguon_label: ["Khoản 2 · Điều 51 · Luật Hôn nhân và Gia đình 2014", ...]
                                              ↓
chat_service returns structured to frontend
                                              ↓
<LegalCitationChip citation="Khoản 2 Điều 51" label="Khoản 2 · Điều 51 · Luật Hôn nhân và Gia đình 2014" sourceUrl="https://phapdien..." />
                                              ↓
User sees: 📜 Khoản 2 · Điều 51 · Luật Hôn nhân và Gia đình 2014  → click → mở văn bản gốc
```

## Components

### A. `backend/scripts/reingest_with_citation_fields.py` (new, ~60 lines)

```python
"""Re-ingest Qdrant collection with citation-related fields preserved.

Destructive: drops and rebuilds the legal_articles collection plus BM25 index.
Run once after merging this change, then delete the script or keep for future migrations.
"""
from datasets import load_dataset
from services.qdrant_service import (
    QDRANT_COLLECTION_NAME,
    get_qdrant_client,
    ingest_articles,
)
from services.bm25_index import build_index, save_index

# 1. Load dataset
ds = load_dataset("tmquan/phapdien-moj-gov-vn", "articles", split="train")

# 2. Transform to article dicts (matching existing split_legal_chunks output shape)
articles = []
for row in ds:
    # article_id must be stable: use article_anchor or hash of source_url
    article_id = row["article_anchor"]  # or build from source_url
    article = {
        "id": article_id,
        "doc_id": row["subject_id"],
        "title": row["article_title"],
        "content_text": row["content_text"],
        "chunk_index": 0,
        "source_url": row["source_url"],
        # NEW fields:
        "source_note_text": row.get("source_note_text", ""),
        "article_title": row.get("article_title", ""),
        "chapter_title": row.get("chapter_title", ""),
        "source_links": row.get("source_links", []),
        # Legacy fields (Qdrant expects them):
        "so_ky_hieu": "",
        "loai_van_ban": "",  # not in dataset, kept for back-compat
        "co_quan_ban_hanh": "",
        "tinh_trang_hieu_luc": "",
        "linh_vuc": row.get("topic_title", ""),
        "nganh": row.get("subject_title", ""),
        "article_label": row.get("article_title", ""),
        "chapter_label": row.get("chapter_title", ""),
        "chunk_level": "article",
        "total_chunks": 1,
    }
    articles.append(article)

# 3. Wipe + re-ingest
client = get_qdrant_client()
client.delete_collection(QDRANT_COLLECTION_NAME)
# Recreate collection (matching the schema expected by existing code)
# ... (or call existing init_collection helper if available)
ingest_articles(articles)

# 4. Rebuild BM25
bm25, meta = build_index()
save_index(bm25, meta)
print(f"Re-ingested {len(articles)} articles")
```

**Note:** the script must be reviewed carefully against the existing `ingest_articles()` payload schema to ensure we don't break callers like `citation_verifier.py` and `bm25_index.py` that read `article_label`, `chapter_label`, `source_url`, `content_text`.

### B. `backend/services/citation_enricher.py` (new, ~60 lines)

```python
"""Build rich citation labels (article + law reference) from retrieved chunks."""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Same regex family as citation_verifier.py
_ARTICLE_RE = re.compile(r"Điều\s+(\w+)", re.IGNORECASE)
_KHOAN_RE = re.compile(r"Khoản\s+(\w+)", re.IGNORECASE)
_DIEM_RE = re.compile(r"Điểm\s+(\w+)", re.IGNORECASE)


def _find_matching_context(citation: str, contexts: list[dict]) -> dict | None:
    """Return the context whose article_label/content matches the citation."""
    m = _ARTICLE_RE.search(citation or "")
    if not m:
        return None
    article_token = m.group(1).lower()
    for c in contexts:
        label = (c.get("article_label") or "").lower()
        content = (c.get("content_text") or "").lower()
        if article_token in label or f"điều {article_token}" in content:
            return c
    return None


def _extract_law_reference(source_note_text: str) -> str | None:
    """Pull '(Điều X Luật số NN/NN/QHYY ...)' out of source_note_text.

    Returns the inner reference string, or None if not found.
    Example input: '(Điều 1 Luật số 32/2004/QH11 An ninh Quốc gia ... ngày 03/12/2004)'
    Example output: 'Luật số 32/2004/QH11 An ninh Quốc gia'
    """
    if not source_note_text:
        return None
    # Pattern: capture from "Luật số ..." until first comma or "ngày"
    m = re.search(r"(Luật[^\n,]*?)(?:,|ngày)", source_note_text)
    if m:
        return m.group(1).strip()
    # Fallback: return whole note minus the parens
    return source_note_text.strip("()").strip() or None


def _build_label(citation: str, matched: dict | None) -> str:
    """Combine parsed parts + law reference from source_note_text."""
    if not citation or citation.startswith("http"):
        return citation
    parts = []
    if (m := _DIEM_RE.search(citation)):
        parts.append(f"Điểm {m.group(1)}")
    if (m := _KHOAN_RE.search(citation)):
        parts.append(f"Khoản {m.group(1)}")
    if (m := _ARTICLE_RE.search(citation)):
        parts.append(f"Điều {m.group(1)}")
    if matched:
        ref = _extract_law_reference(matched.get("source_note_text", ""))
        if ref and ref not in " ".join(parts):
            parts.append(ref)
    return " · ".join(parts) if len(parts) > 1 else citation


def enrich_citations(structured: dict, contexts: list[dict[str, Any]]) -> dict:
    """Add structured['trich_dan_nguon_label'] parallel to trich_dan_nguon.
    Mutates and returns structured."""
    cited: list[str] = structured.get("trich_dan_nguon") or []
    labels: list[str] = [
        _build_label(cite, _find_matching_context(cite, contexts)) for cite in cited
    ]
    structured["trich_dan_nguon_label"] = labels
    return structured
```

### C. `backend/services/chat_service.py` — wire enricher

Insert 1 line after `verify_citations(...)`:
```python
from services.citation_enricher import enrich_citations
structured = verify_citations(structured, contexts)
structured = enrich_citations(structured, contexts)
```

### D. Synthesizer prompt edit (location TBD)

Read `backend/services/prompt_loader.py` to find the file path. Likely `backend/prompts/synthesizer.md` or similar. Add per-field length guidance and forbid URL in `trich_dan_nguon`.

### E. Frontend 2 small changes

```ts
// frontend/lib/api.ts
export interface LawyerSection {
  // ... existing fields
  trich_dan_nguon_label?: string[]
}
```

```tsx
// frontend/components/chat/legal-citation-chip.tsx
interface LegalCitationChipProps {
  citation: string
  label?: string  // pre-formatted full reference, set by enricher
  sourceUrl?: string
}
// In render, use `label` if provided, else fall back to parsed label
```

## Error handling

- **No matching context**: enricher returns raw citation string
- **Citation is a URL**: enricher passes through unchanged; frontend already handles as "Mở văn bản gốc" link
- **`source_note_text` empty**: enricher returns partial label (just Điều/Khoản/Điểm) — still better than nothing
- **Re-ingest fails midway**: re-runnable (delete + recreate is idempotent)
- **No articles have `source_note_text`**: enricher always falls back to raw — no improvement, no regression

## Testing strategy

1. **Unit test enricher** (pytest, `tests/services/test_citation_enricher.py`):
   - Citation "Khoản 2 Điều 51" + matched context with `source_note_text="(Điều 51 Luật số 32/2004/QH11 An ninh Quốc gia...)"` → label `"Khoản 2 · Điều 51 · Luật số 32/2004/QH11 An ninh Quốc gia"`
   - Citation "Điều 999" (no match) → label = raw citation
   - Citation "https://..." → label = URL (no enrichment)
   - Citation with empty `source_note_text` → label = parsed parts only
2. **Re-ingest smoke test** (manual): run script, verify Qdrant has new fields, run 1 chat query, verify response has `trich_dan_nguon_label`
3. **Integration test** (curl + browser): verify chip shows "Khoản X · Điều Y · Luật Z..." in the lawyer response view
4. **Regression**: existing `test_citation_verifier.py`, `test_chat_service.py` (197+ tests) still pass

## Rollout

Two PRs (cleaner history):
- **PR 1**: re-ingest script + ingest_articles payload update. Manual run by user. Re-build BM25. Verify Qdrant has new fields.
- **PR 2**: enricher + prompt + frontend (independent of ingest; uses new fields when available, falls back gracefully if old).

Or single PR if user prefers — both work because the enricher is defensive.

## Open questions

- (To verify during implementation) Where is the synthesizer prompt file? — need to read `prompt_loader.py`
- (To verify) Does `ingest_articles` get called with `chunk_index` per article, or is the dataset already at article granularity? — affects whether we need to call `split_legal_chunks` or feed articles directly
- (To verify) Exact field name in dataset for stable article ID — `article_anchor` looks hashy; `id` may not exist
