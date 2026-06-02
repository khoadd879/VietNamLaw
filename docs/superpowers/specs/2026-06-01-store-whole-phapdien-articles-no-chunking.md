# Store Whole `phapdien-moj` Articles (No Chunking) as Qdrant Points

> **Status:** Draft
> **Date:** 2026-06-01
> **Author:** Khoa (with Claude)
> **Related code:** `scripts/ingest_phapdien_moj.py`, `backend/services/qdrant_service.py`, `backend/services/bm25_index.py`, `backend/services/crossref_walker.py`

## Problem

The `tmquan/phapdien-moj-gov-vn` dataset is already pre-cleaned: each row is **one article** (một điều luật) with full content. Currently the ingest script still runs the heavy `split_legal_chunks` splitter (designed for raw HTML pages) and a 30-chunk cap on top of that. The resulting Qdrant collection has these problems:

1. **Payload fields are incomplete** — 7 of the 17 dataset fields are dropped (`subject_id`, `topic_id`, `topic_number`, `subject_number`, `article_anchor`, `source_links`, `content_char_len`, `content_word_count`, `scraped_at`).
2. **Synthetic metadata is added** — `chunk_index`, `total_chunks`, `chunk_level`, `chapter_label` (filled from `chapter_title` even when it is empty for most rows).
3. **Article fragmentation** — one dataset row can become up to 30 Qdrant points, breaking 1-to-1 traceability with the source row, hurting BM25 scoring, and complicating citation.
4. **Renamed fields** — `source_note_text` becomes `source_note`, `related_note_text` becomes `related_note`, and `chapter_title`/`article_title` are aliased to `chapter_label`/`article_label`.

## Goal

Store each dataset row as exactly one Qdrant point, preserving all 17 source fields, with no synthetic chunk metadata. Embedding the whole `content_text` directly, capped at a length the embedder can handle (bge-m3 supports up to 8192 tokens ≈ ~20K Vietnamese chars).

## Non-Goals

- Re-chunking or re-ranking strategies.
- Changing the embedding model (still `bge-m3` via Ollama).
- Migrating the older `th1nhng0/vietnamese-legal-documents` dataset (kept as-is in `scripts/ingest_phapdien.py`).
- Changing the BM25/Hybrid/RAG retrieval pipeline (it will work transparently with the new payload shape — no `chunk_index`, no `chunk_level`, no `chapter_label`/`article_label`).

## Dataset → Payload Mapping (1:1)

For every row in `articles` subset, build a point with `id = uuid5(NAMESPACE_URL, f"phapdien:{article_anchor}")` and payload:

| Dataset field | Payload key | Type | Notes |
| --- | --- | --- | --- |
| `article_anchor` | `article_anchor` | string | Used as the canonical doc key |
| `article_title` | `article_title` | string | |
| `content_text` | `content_text` | string | The text passed to the embedder |
| `content_char_len` | `content_char_len` | int | |
| `content_word_count` | `content_word_count` | int | |
| `chapter_title` | `chapter_title` | string | Empty string when null |
| `subject_id` | `subject_id` | string | UUID |
| `subject_number` | `subject_number` | int | |
| `subject_title` | `subject_title` | string | |
| `topic_id` | `topic_id` | string | UUID |
| `topic_number` | `topic_number` | int | |
| `topic_title` | `topic_title` | string | |
| `source_note_text` | `source_note_text` | string | |
| `source_links` | `source_links` | list[{text, href}] | Stored as-is |
| `related_note_text` | `related_note_text` | string | |
| `source_url` | `source_url` | string | |
| `scraped_at` | `scraped_at` | string | ISO timestamp |

**Removed synthetic fields (not stored):** `chunk_index`, `total_chunks`, `chunk_level`, `chapter_label`, `article_label`, `khoan_label`, `title` (alias), `relationships` (no equivalent in this dataset).

## Embedding Strategy

- **Cap at 10,000 chars** before embedding. The dataset has only 336 rows above 10K chars (0.5%); the top 20 outliers are clearly corrupted/legal-compilation dumps (8 MB, 530K, 447K chars). Anything beyond 10K is dropped from ingestion with a warning so the embedder's 8K-token limit is never exceeded.
- **Drop empty `content_text` rows** (406 rows / 0.6%) — these are bookmarks without body.
- **For long content (1500–10000 chars)**: still store whole, embed whole. bge-m3 handles 8K tokens (~20K chars Vietnamese). Tested: median is 750 chars, 95th percentile ≈ 3.5K, 99th percentile ≈ 10K.
- **Text sent to embedder** is `content_text` (unchanged). No template wrapping.

## Collection Schema

- **Name:** `QDRANT_COLLECTION_NAME` (env-driven, default `legal_articles`).
- **Vector:** size 1024, COSINE (unchanged).
- **Payload indexes (keyword)** on the fields we filter on: `subject_title`, `topic_title`, `chapter_title`, `source_url`, `article_anchor`.
- **Collection recreation**: required. The new payload schema is incompatible with the old chunked one (different `id` derivation, different fields). Operators must drop and recreate.

## Retrieval Compatibility

- `search_legal_context` continues to read `content_text`, `source_url`, and `score`. No code path requires `chunk_index`/`chunk_level` to function.
- `bm25_index._scroll_all_points` reads `content_text`, `title`, `article_label`, `chapter_label` — only the last two are absent in the new payload. We will switch it to read `article_title` and `chapter_title` instead, with a fallback to empty string.
- `crossref_walker._fetch_by_ids` reads the same fields — same switch.
- `hybrid_search` / `chat_service` / `two_stage_reasoner` only need `content_text` + `source_url` + `score` — already supported.

## Verification

- After re-ingestion, scroll the full collection and assert: `len(points) == 64,464 - 406 empty - <dropped for length>`.
- Assert each point has the full 17-field payload (no `chunk_index`, no `chunk_level`).
- Run `search_legal_context("điều kiện ly hôn đơn phương")` and confirm top results point to real `Điều` titles and contain `source_url`/`scraped_at`.

## Out-of-Scope Follow-ups

- Future: re-evaluate `RETRIEVAL_TOP_K` once one point = one article (chunks-per-article bias is gone).
- Future: add `subject_title` / `topic_title` as filterable fields in `search_legal_context`.
