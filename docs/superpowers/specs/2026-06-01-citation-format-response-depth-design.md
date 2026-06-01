# Design: Citation Format & Response Depth

**Date:** 2026-06-01
**Status:** Approved (user selected Approach A)
**Author:** Claude + Khoa

## Context

User feedback (post-Sprint 3): citations show up as raw URLs (`https://phapdien.moj.gov.vn/...`) instead of legal-reference style ("Điều 51 Luật Hôn nhân và gia đình 2014"). Responses also feel thin — short 1-2 paragraph analyses without concrete dẫn chiếu.

Current state:
- `trich_dan_nguon` is whatever the LLM writes verbatim (sometimes a URL, sometimes "Điều 51", sometimes nothing)
- Frontend `LegalCitationChip` parses the string with regex to extract Điều/Khoản/Điểm but has no source-of-truth for the law name
- `phan_tich_phap_ly` field gets whatever the LLM feels like writing — no length guidance in the synthesizer prompt

## Goals

1. Citations render as proper legal references: `Điều X · Luật Y năm Z` (with Khoản/Điểm when present), still click-through to the source URL
2. Responses are moderately longer and more structured — explicit dẫn chiếu điều luật cụ thể, phương án có bước hành động
3. Existing UX (chips, expand-to-link) preserved — just better content

## Non-goals

- Re-architecting the retrieval pipeline
- Caching the enriched citation labels
- Adding new structured fields beyond what the LLM schema already has
- Full Vietnamese typography / diacritics cleanup (separate concern)

## Approach: Backend enrich citations + tighten prompt (Approach A)

### Architecture

Two changes, separate concerns:

**Change 1 — Citation enrichment (backend)**
- New module: `backend/services/citation_enricher.py`
- After `verify_citations(...)`, run `enrich_citations(structured, contexts)`
- For each string in `structured.trich_dan_nguon`:
  1. Parse "Điều X" / "Khoản Y" / "Điểm Z" with the same regex used in `citation_verifier.py`
  2. Find the matching context chunk by article_label match (or fuzzy: scan all contexts for the article number in `content_text` or `article_label`)
  3. Build label parts: `[Điểm Z, Khoản Y, Điều X, Luật Y năm Z]` — only include non-empty parts
  4. Append enriched label to a new field `structured.trich_dan_nguon_label: string[]` (parallel array, same length)
  5. URLs in the original `trich_dan_nguon` are passed through unchanged; we still produce a label for them if we can find a matching chunk

**Change 2 — Prompt tightening (backend)**
- Edit the file pointed to by `SYNTHESIZER_PROMPT` constant (likely `prompts/synthesizer.md` or a DB row — to be confirmed when reading the prompt_loader)
- Add explicit per-field length and content guidance:
  - `phan_tich_phap_ly`: 2-4 đoạn, mỗi đoạn 80-150 từ, dẫn chiếu cụ thể Điều/Khoản/Điểm khi áp dụng
  - `phuong_an_khuyen_nghi`: mỗi phương án 1-3 câu, có bước hành động cụ thể
  - `rui_ro_can_luu_y`: mỗi rủi ro 1-2 câu, nêu hậu quả pháp lý
  - `cau_hoi_hoi_them`: câu ngắn gọn, tập trung vào facts còn thiếu
  - Reminder: `trich_dan_nguon` phải là string mô tả điều luật ("Điều 51 Luật Hôn nhân và gia đình 2014"), KHÔNG phải URL

**Change 3 — Frontend render (small)**
- `frontend/lib/api.ts`: add `trich_dan_nguon_label?: string[]` to `LawyerSection` interface
- `frontend/components/chat/legal-citation-chip.tsx`: when `label` prop provided, use it instead of building from `parseCitation`

## Data flow

```
LLM (Groq)  ──returns──>  structured.trich_dan_nguon: ["Điều 51 - Luật HNGĐ", "Điều 56 Luật HNGĐ"]
                              │
                              ▼
verify_citations()  ──drops unverifiable──>  filtered list
                              │
                              ▼
enrich_citations(structured, contexts)  ──builds labels──>  structured.trich_dan_nguon_label: ["Điều 51 · Luật Hôn nhân và gia đình 2014", ...]
                              │
                              ▼
chat_service returns structured to frontend
                              │
                              ▼
LawyerResponseView  ──passes label to chip──>  <LegalCitationChip citation="Điều 51" label="Điều 51 · Luật Hôn nhân và gia đình 2014" sourceUrl="..." />
                              │
                              ▼
User sees: 📜 Điều 51 · Luật Hôn nhân và gia đình 2014  → click → mở văn bản gốc
```

## Components

### 1. `backend/services/citation_enricher.py` (new, ~80 lines)

```python
"""Enrich LLM-cited article strings with full legal labels (law name + year)."""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Same regex family as citation_verifier.py; non-greedy to keep phrases short.
_ARTICLE_RE = re.compile(r"Điều\s+(\w+)", re.IGNORECASE)
_KHOAN_RE = re.compile(r"Khoản\s+(\w+)", re.IGNORECASE)
_DIEM_RE = re.compile(r"Điểm\s+(\w+)", re.IGNORECASE)


def _find_matching_context(citation: str, contexts: list[dict]) -> dict | None:
    """Return the context whose article_label matches the citation, or None."""
    m = _ARTICLE_RE.search(citation or "")
    if not m:
        return None
    article_num = m.group(1).lower()
    for c in contexts:
        label = (c.get("article_label") or "").lower()
        if article_num in label:
            return c
    return None


def _format_law_name(loai_van_ban: str) -> str | None:
    """Turn 'Luật Hôn nhân và gia đình 2014' into 'Luật Hôn nhân và gia đình 2014'.
    Returns None if empty/looks like a URL."""
    if not loai_van_ban or loai_van_ban.startswith("http"):
        return None
    return loai_van_ban.strip()


def _build_label(citation: str, matched: dict | None) -> str | None:
    """Build 'Điều X · Khoản Y · Luật Z năm N'. Returns None if we can't enrich."""
    if not citation or citation.startswith("http"):
        return None
    diem_m = _DIEM_RE.search(citation)
    khoan_m = _KHOAN_RE.search(citation)
    article_m = _ARTICLE_RE.search(citation)
    parts = []
    if diem_m:
        parts.append(f"Điểm {diem_m.group(1)}")
    if khoan_m:
        parts.append(f"Khoản {khoan_m.group(1)}")
    if article_m:
        parts.append(f"Điều {article_m.group(1)}")
    if matched:
        law = _format_law_name(matched.get("loai_van_ban", ""))
        if law:
            parts.append(law)
    return " · ".join(parts) if len(parts) > 1 else None


def enrich_citations(structured: dict, contexts: list[dict[str, Any]]) -> dict:
    """Add structured['trich_dan_nguon_label'] parallel to trich_dan_nguon.
    Mutates and returns structured."""
    cited: list[str] = structured.get("trich_dan_nguon") or []
    labels: list[str] = []
    for cite in cited:
        matched = _find_matching_context(cite, contexts)
        label = _build_label(cite, matched)
        labels.append(label or cite)  # fall back to raw citation
    structured["trich_dan_nguon_label"] = labels
    return structured
```

### 2. `backend/services/chat_service.py` — wire in enricher

```python
# After verify_citations(...)
from services.citation_enricher import enrich_citations
structured = enrich_citations(structured, contexts)
```

Plus update the `cited_sources` mapping: keep `sources[i]` aligned with `trich_dan_nguon[i]`, not with `contexts` order, so chip receives the right URL for each citation.

### 3. Synthesizer prompt edit

Find the file `prompt_loader.py` references. Likely `prompts/synthesizer.md` or similar. Add length guidance per field and a "no URLs in trich_dan_nguon" instruction.

### 4. Frontend `lib/api.ts` + `legal-citation-chip.tsx`

```ts
// api.ts
export interface LawyerSection {
  // ... existing fields
  trich_dan_nguon_label?: string[]  // parallel to trich_dan_nguon
}
```

```tsx
// legal-citation-chip.tsx
interface LegalCitationChipProps {
  citation: string
  label?: string  // pre-formatted "Điều X · Luật Y" if enricher produced one
  sourceUrl?: string
}
// In render: <span>{label ?? parsedLabel}</span>
```

## Error handling

- **No matching context**: enricher falls back to raw `citation` string (chip still works, just without law name)
- **Citation is a URL**: enricher skips enrichment, label = URL (frontend already handles this case — shows "Mở văn bản gốc" link)
- **LLM returns empty trich_dan_nguon**: enricher returns empty labels list, no-op
- **Malformed citation (no "Điều X" pattern)**: enricher returns the raw string, no crash

## Testing strategy

1. **Unit test enricher** (pytest):
   - Citation "Điều 51 - Luật HNGĐ" + matching context with `loai_van_ban="Luật Hôn nhân và gia đình 2014"` → label includes "Điều 51 · Luật Hôn nhân và gia đình 2014"
   - Citation "Điều 999" (no matching context) → label = raw citation
   - Citation "https://example.com" → label = URL (no enrichment)
   - Citation "Khoản 2 Điều 51" → label includes "Khoản 2 · Điều 51 · ..."
2. **Manual integration** (curl + browser):
   - Send chat message, verify response includes `trich_dan_nguon_label` field
   - Open browser, verify chip shows "Điều X · Luật Y năm Z" not raw URL
3. **Regression**: existing `test_citation_verifier.py` still passes (enricher is additive)

## Rollout

Single PR. Backend changes are additive (new file + 2 line integration + 1 prompt edit). Frontend changes are additive (new optional prop). No migration needed.

## Open questions

- (To verify during implementation) Exact location of the synthesizer prompt file — need to read `prompt_loader.py`
- (To verify) Whether the `cited_sources` list is currently in citation-order or context-order — affects whether chip URL alignment breaks
