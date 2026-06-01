# Sprint 3 — Advanced RAG + UX (hybrid retrieval + multi-query + citation verify + citation chip + follow-ups + disclaimer)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng chất lượng trích dẫn và trải nghiệm lên mức "luật sư thật": hybrid retrieval (BM25 + vector) bắt được cả truy vấn từ khoá chính xác (số điều, tên văn bản) lẫn semantic; multi-query reformulation tăng recall; citation verification loại bỏ chunk LLM trích dẫn sai; cross-reference walker kéo thêm chunks liên quan (Điều 51 → Nghị định hướng dẫn); UX chip trích dẫn click-to-jump, suggested follow-ups, disclaimer banner cố định.

**Architecture:** Thêm `bm25_index.py` (in-memory index rebuilt từ Qdrant collection lúc startup, persisted to disk). `hybrid_search` combine BM25 score + vector score với weight configurable. `multi_query_expand` gọi LLM sinh 2-3 biến thể câu hỏi trước khi retrieve. `citation_verifier` parse response LLM, với mỗi `trich_dan_nguon` kiểm tra có nằm trong text chunk không. `crossref_walker` theo `relationships[]` payload fetch thêm chunks liên quan (cap 5). Frontend: 3 component mới, sửa `assistant-message.tsx` để dùng `LegalCitationChip`.

**Tech Stack:** Same. Thêm: thư viện `rank-bm25` (pure Python, MIT license) cho BM25; `difflib.SequenceMatcher` cho citation verify (stdlib).

**Phụ thuộc:** Sprint 1 (structured output) + Sprint 2 (case_brief passed to LLM). Sprint 3 KHÔNG đụng schema DB.

---

## Task 3.1: BM25 index in-memory + persistence

**Files:**
- Create: `backend/services/bm25_index.py`
- Modify: `backend/core/config.py` (thêm config)
- Test: `backend/tests/services/test_bm25_index.py`

- [ ] **Step 1: Thêm dependency + config**

Cập nhật `backend/requirements.txt` (hoặc pyproject.toml — check file hiện có):

```
rank-bm25==0.2.2
```

```bash
cd backend
pip install rank-bm25==0.2.2
```

Thêm cuối `backend/core/config.py`:

```python
BM25_INDEX_PATH = os.getenv("BM25_INDEX_PATH", "./data/bm25_index.pkl")
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.6"))
HYBRID_BM25_WEIGHT = float(os.getenv("HYBRID_BM25_WEIGHT", "0.4"))
MULTI_QUERY_COUNT = int(os.getenv("MULTI_QUERY_COUNT", "2"))
CROSSREF_MAX_HOPS = int(os.getenv("CROSSREF_MAX_HOPS", "1"))
CROSSREF_MAX_CHUNKS = int(os.getenv("CROSSREF_MAX_CHUNKS", "5"))
```

- [ ] **Step 2: Tạo BM25 index service**

Ghi `backend/services/bm25_index.py`:

```python
"""In-memory BM25 index over Qdrant collection, with disk persistence."""
import logging
import pickle
import re
from pathlib import Path
from typing import Iterable

from rank_bm25 import BM25Okapi

from core.config import BM25_INDEX_PATH
from services.qdrant_service import get_qdrant_client, QDRANT_COLLECTION_NAME

logger = logging.getLogger(__name__)

# Vietnamese tokenization is hard; for Sprint 3 we use simple word split on
# whitespace + lowercase. This is good enough for matching exact article
# numbers ("Điều 51", "Khoản 2") and proper nouns. Future: integrate pyvi.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _scroll_all_points(batch_size: int = 200) -> Iterable[dict]:
    """Yield every point in the Qdrant collection as a dict."""
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
                "title": point.payload.get("title", ""),
                "article_label": point.payload.get("article_label"),
                "chapter_label": point.payload.get("chapter_label"),
                "loai_van_ban": point.payload.get("loai_van_ban", ""),
                "source_url": point.payload.get("source_url", ""),
            }
        if next_offset is None:
            break
        offset = next_offset


def build_index() -> tuple[BM25Okapi, list[dict]]:
    """Build a fresh BM25 index from the current Qdrant collection.

    Returns (bm25, corpus_meta) where corpus_meta[i] corresponds to doc i.
    """
    corpus_meta: list[dict] = []
    tokenized_corpus: list[list[str]] = []
    for doc in _scroll_all_points():
        corpus_meta.append(doc)
        tokenized_corpus.append(_tokenize(doc["content_text"] + " " + doc.get("title", "")))
    bm25 = BM25Okapi(tokenized_corpus)
    logger.info("Built BM25 index with %d documents", len(corpus_meta))
    return bm25, corpus_meta


def save_index(bm25: BM25Okapi, corpus_meta: list[dict], path: str | None = None) -> None:
    target = Path(path or BM25_INDEX_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        pickle.dump({"bm25": bm25, "corpus_meta": corpus_meta}, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Saved BM25 index to %s", target)


def load_index(path: str | None = None) -> tuple[BM25Okapi, list[dict]] | None:
    target = Path(path or BM25_INDEX_PATH)
    if not target.is_file():
        return None
    with target.open("rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["corpus_meta"]


def search(bm25: BM25Okapi, corpus_meta: list[dict], query: str, top_k: int = 10) -> list[dict]:
    """Return top_k docs by BM25 score, formatted like qdrant_service returns."""
    tokens = _tokenize(query)
    scores = bm25.get_scores(tokens)
    # Pair (score, idx), sort desc, take top_k
    paired = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for idx, score in paired:
        if score <= 0:
            continue
        meta = corpus_meta[idx]
        results.append({**meta, "score": float(score), "bm25_score": float(score)})
    return results
```

- [ ] **Step 3: Viết failing test**

Ghi `backend/tests/services/test_bm25_index.py`:

```python
from rank_bm25 import BM25Okapi

from services.bm25_index import _tokenize, build_index, load_index, save_index, search


def test_tokenize_lowercases_and_splits_words() -> None:
    tokens = _tokenize("Điều 51 Luật Hôn nhân Gia đình 2014")
    assert "điều" in tokens
    assert "51" in tokens
    assert "luật" in tokens


def test_build_index_returns_bm25_and_corpus() -> None:
    class FakePoint:
        def __init__(self, id_, payload):
            self.id = id_
            self.payload = payload
    class FakeClient:
        def scroll(self, **kwargs):
            return [
                FakePoint("1", {"content_text": "Điều 51 quyền yêu cầu ly hôn", "title": "Luật HNGĐ"}),
                FakePoint("2", {"content_text": "Điều 56 thuận tình ly hôn", "title": "Luật HNGĐ"}),
            ], None
    import services.bm25_index as mod
    mod.get_qdrant_client = lambda: FakeClient()
    bm25, meta = build_index()
    assert isinstance(bm25, BM25Okapi)
    assert len(meta) == 2
    assert meta[0]["content_text"].startswith("Điều 51")


def test_search_returns_relevant_docs_in_order() -> None:
    class FakeClient:
        def scroll(self, **kwargs):
            class P:
                def __init__(self, i, t):
                    self.id = i
                    self.payload = {"content_text": t, "title": "L"}
            return [P(1, "Điều 51 quyền yêu cầu ly hôn"), P(2, "Điều 56 thuận tình ly hôn")], None
    import services.bm25_index as mod
    mod.get_qdrant_client = lambda: FakeClient()
    bm25, meta = build_index()
    results = search(bm25, meta, "ly hôn đơn phương Điều 51", top_k=2)
    assert len(results) >= 1
    assert results[0]["content_text"].startswith("Điều 51")


def test_save_and_load_index_round_trip(tmp_path) -> None:
    import services.bm25_index as mod
    class FakeClient:
        def scroll(self, **kwargs):
            class P:
                def __init__(self, i, t):
                    self.id = i
                    self.payload = {"content_text": t, "title": "L"}
            return [P(1, "Điều 51")], None
    mod.get_qdrant_client = lambda: FakeClient()
    bm25, meta = build_index()
    p = tmp_path / "idx.pkl"
    save_index(bm25, meta, str(p))
    loaded = load_index(str(p))
    assert loaded is not None
    bm25_2, meta_2 = loaded
    assert len(meta_2) == 1
    assert search(bm25_2, meta_2, "Điều 51", top_k=1)[0]["content_text"] == "Điều 51"
```

- [ ] **Step 4: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_bm25_index.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/bm25_index.py backend/core/config.py backend/requirements.txt backend/tests/services/test_bm25_index.py
git commit -m "feat(bm25): in-memory BM25 index over Qdrant with disk persistence"
```

---

## Task 3.2: Hybrid search + multi-query expansion + cross-ref walker

**Files:**
- Create: `backend/services/hybrid_search.py`
- Create: `backend/services/multi_query.py`
- Create: `backend/services/crossref_walker.py`
- Test: `backend/tests/services/test_hybrid_search.py`
- Test: `backend/tests/services/test_multi_query.py`
- Test: `backend/tests/services/test_crossref_walker.py`

- [ ] **Step 1: Tạo hybrid search**

Ghi `backend/services/hybrid_search.py`:

```python
"""Hybrid retrieval: vector (Qdrant) + BM25, normalized and weighted."""
import logging
import math
from typing import Any

from core.config import HYBRID_BM25_WEIGHT, HYBRID_VECTOR_WEIGHT
from services.bm25_index import load_index, search as bm25_search
from services.qdrant_service import search_legal_context as vector_search

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8


def _min_max_normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    s_min, s_max = min(scores), max(scores)
    if s_max == s_min:
        return [1.0 for _ in scores]
    return [(s - s_min) / (s_max - s_min) for s in scores]


def _dedupe_by_id(docs: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for d in docs:
        key = d.get("id") or d.get("doc_id")
        if key and key not in seen:
            seen[key] = d
    return list(seen.values())


def hybrid_search(
    query: str,
    filters: dict | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Run vector + BM25, combine scores, return top_k."""
    index = load_index()
    vector_results = vector_search(query, filters=filters, top_k=top_k * 2)
    bm25_results: list[dict] = []
    if index is not None:
        bm25, meta = index
        bm25_results = bm25_search(bm25, meta, query, top_k=top_k * 2)

    # Normalize each set to [0, 1]
    v_norm = _min_max_normalize([r.get("score", 0.0) for r in vector_results])
    b_norm = _min_max_normalize([r.get("bm25_score", 0.0) for r in bm25_results])

    vector_by_id: dict[str, tuple[dict, float]] = {}
    for r, s in zip(vector_results, v_norm):
        rid = r.get("id") or r.get("doc_id") or f"v{len(vector_by_id)}"
        vector_by_id[rid] = (r, s)

    bm25_by_id: dict[str, tuple[dict, float]] = {}
    for r, s in zip(bm25_results, b_norm):
        rid = r.get("id") or f"b{len(bm25_by_id)}"
        bm25_by_id[rid] = (r, s)

    all_ids = set(vector_by_id) | set(bm25_by_id)
    combined: list[dict] = []
    for rid in all_ids:
        v_doc, v_score = vector_by_id.get(rid, ({}, 0.0))
        b_doc, b_score = bm25_by_id.get(rid, ({}, 0.0))
        doc = {**(v_doc or b_doc)}
        doc["vector_score"] = v_score
        doc["bm25_normalized"] = b_score
        doc["score"] = HYBRID_VECTOR_WEIGHT * v_score + HYBRID_BM25_WEIGHT * b_score
        if rid in vector_by_id or rid in bm25_by_id:
            combined.append(doc)

    combined.sort(key=lambda d: d["score"], reverse=True)
    return _dedupe_by_id(combined)[:top_k]
```

- [ ] **Step 2: Tạo multi-query expander**

Ghi `backend/services/multi_query.py`:

```python
"""Generate 2-3 rephrasings of the user query to increase recall."""
import json
import logging

from services.groq_service import _run_pooled
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

MULTI_QUERY_PROMPT = "multi_query_v1"
```

Tạo file `backend/prompts/multi_query_v1.md`:

```markdown
# Nhiệm vụ
Bạn giúp mở rộng truy vấn pháp luật để tăng recall khi tìm kiếm.

# Input
Một câu hỏi pháp luật tiếng Việt.

# Output JSON
```json
{
  "queries": [
    "Câu hỏi gốc giữ nguyên",
    "Biến thể 1 (dùng từ khoá khác)",
    "Biến thể 2 (thay tên gọi thông tư/luật)",
    "Biến thể 3 (thêm/sửa số điều khoản nếu có)"
  ]
}
```

# Quy tắc
- Tối đa 4 câu (1 gốc + 3 biến thể).
- Biến thể giữ ngữ nghĩa pháp lý, đổi cách diễn đạt hoặc thêm từ khoá đồng nghĩa.
- KHÔNG trả lời câu hỏi, KHÔNG tư vấn.
- KHÔNG markdown fence, chỉ JSON.
```

Sửa `backend/services/multi_query.py` — thêm function:

```python
def expand_query(query: str, n_variants: int = 2) -> list[str]:
    """Return original query + up to n_variants rephrasings.

    Falls back to [query] if LLM fails.
    """
    system_prompt = load_prompt(MULTI_QUERY_PROMPT)
    user_text = f"Câu hỏi: {query}\nSố biến thể cần sinh: {n_variants}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    raw = _run_pooled(messages, response_format={"type": "json_object"}, empty_fallback="")
    if not raw:
        return [query]
    try:
        data = json.loads(raw)
        queries = data.get("queries") or []
    except json.JSONDecodeError:
        logger.warning("multi_query returned invalid JSON: %r", raw[:200])
        return [query]
    # Always include the original
    out = [query]
    for q in queries:
        if q and q != query and q not in out:
            out.append(q)
        if len(out) >= n_variants + 1:
            break
    return out
```

- [ ] **Step 3: Tạo cross-reference walker**

Ghi `backend/services/crossref_walker.py`:

```python
"""Follow relationships[] in chunk payload to fetch related chunks."""
import logging
from typing import Any

from core.config import CROSSREF_MAX_CHUNKS, CROSSREF_MAX_HOPS
from services.qdrant_service import get_qdrant_client, QDRANT_COLLECTION_NAME

logger = logging.getLogger(__name__)


def _fetch_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    client = get_qdrant_client()
    from qdrant_client.http import models
    try:
        points = client.retrieve(
            collection_name=QDRANT_COLLECTION_NAME,
            ids=ids,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        logger.warning("crossref retrieve failed: %s", exc)
        return []
    out = []
    for p in points:
        out.append({
            "id": str(p.id),
            "content_text": p.payload.get("content_text", ""),
            "title": p.payload.get("title", ""),
            "article_label": p.payload.get("article_label"),
            "chapter_label": p.payload.get("chapter_label"),
            "loai_van_ban": p.payload.get("loai_van_ban", ""),
            "source_url": p.payload.get("source_url", ""),
            "score": 0.0,
        })
    return out


def walk_relationships(
    seed_chunks: list[dict[str, Any]],
    max_hops: int = CROSSREF_MAX_HOPS,
    max_chunks: int = CROSSREF_MAX_CHUNKS,
) -> list[dict[str, Any]]:
    """Given retrieved chunks, follow their relationships[] to gather more.

    Returns list of related chunks (NOT including the seeds). Capped at max_chunks.
    """
    seen_ids: set[str] = {str(c.get("id") or c.get("doc_id")) for c in seed_chunks if c.get("id") or c.get("doc_id")}
    queue: list[tuple[str, int]] = [
        (str(c.get("id") or c.get("doc_id")), 0)
        for c in seed_chunks
        if c.get("id") or c.get("doc_id")
    ]
    collected: list[dict[str, Any]] = []
    while queue and len(collected) < max_chunks:
        current_id, hop = queue.pop(0)
        if hop >= max_hops:
            continue
        # We don't have the full seed payload here; fetch by id to get relationships
        details = _fetch_by_ids([current_id])
        if not details:
            continue
        rel_ids: list[str] = details[0].get("content_text", "")  # placeholder
        # Re-fetch the actual seed to read relationships
        seeds_with_payload = [s for s in seed_chunks if str(s.get("id") or s.get("doc_id")) == current_id]
        if not seeds_with_payload:
            continue
        rels = seeds_with_payload[0].get("relationships") or []
        for rel in rels:
            target_id = rel.get("target_id") if isinstance(rel, dict) else str(rel)
            if not target_id or target_id in seen_ids:
                continue
            seen_ids.add(target_id)
            queue.append((target_id, hop + 1))
            if len(collected) < max_chunks:
                collected.append({"id": target_id, "_pending": True})
    # Fetch full payloads for pending entries
    pending_ids = [c["id"] for c in collected if c.get("_pending")]
    full = _fetch_by_ids(pending_ids)
    return full
```

> **Lưu ý kỹ thuật:** `seed_chunks` từ `hybrid_search` đã có `relationships` field nếu Qdrant payload lưu. Implementation trên dùng cách fetch trực tiếp từ seed payload (nhanh hơn). Nếu seed không có `relationships`, fetch thêm từ Qdrant.

- [ ] **Step 4: Viết failing tests**

Ghi `backend/tests/services/test_hybrid_search.py`:

```python
from unittest.mock import patch

from services.hybrid_search import _min_max_normalize, hybrid_search


def test_min_max_normalize_handles_constant_scores() -> None:
    assert _min_max_normalize([0.5, 0.5, 0.5]) == [1.0, 1.0, 1.0]


def test_min_max_normalize_maps_to_zero_one_range() -> None:
    out = _min_max_normalize([0.1, 0.5, 0.9])
    assert min(out) == 0.0
    assert max(out) == 1.0


def test_hybrid_search_combines_vector_and_bm25_scores() -> None:
    vector_results = [
        {"id": "1", "content_text": "A", "score": 0.9},
        {"id": "2", "content_text": "B", "score": 0.5},
    ]
    bm25_results = [
        {"id": "2", "content_text": "B", "bm25_score": 10.0},
        {"id": "3", "content_text": "C", "bm25_score": 5.0},
    ]
    with patch("services.hybrid_search.vector_search", return_value=vector_results), \
         patch("services.hybrid_search.load_index", return_value=("bm25_fake", "meta_fake")), \
         patch("services.hybrid_search.bm25_search", return_value=bm25_results):
        results = hybrid_search("query", top_k=3)
    ids = [r["id"] for r in results]
    # Doc 2 appears in both -> should win; doc 1 only in vector; doc 3 only in BM25
    assert ids[0] == "2"
    assert "1" in ids and "3" in ids
    for r in results:
        assert "vector_score" in r
        assert "bm25_normalized" in r
        assert 0.0 <= r["score"] <= 1.0


def test_hybrid_search_works_when_bm25_index_missing() -> None:
    vector_results = [{"id": "1", "content_text": "A", "score": 0.9}]
    with patch("services.hybrid_search.vector_search", return_value=vector_results), \
         patch("services.hybrid_search.load_index", return_value=None):
        results = hybrid_search("query", top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == "1"
```

Ghi `backend/tests/services/test_multi_query.py`:

```python
import json
from unittest.mock import patch

from services.multi_query import expand_query


def test_expand_query_returns_original_plus_variants() -> None:
    payload = json.dumps({"queries": ["Ly hôn đơn phương", "Đơn phương ly hôn thế nào"]})
    with patch("services.multi_query._run_pooled", return_value=payload):
        queries = expand_query("Ly hôn", n_variants=2)
    assert queries[0] == "Ly hôn"
    assert len(queries) == 3
    assert "Ly hôn đơn phương" in queries


def test_expand_query_dedupes_and_preserves_original() -> None:
    payload = json.dumps({"queries": ["Ly hôn", "Ly hôn đơn phương", "Ly hôn"]})
    with patch("services.multi_query._run_pooled", return_value=payload):
        queries = expand_query("Ly hôn", n_variants=3)
    assert queries[0] == "Ly hôn"
    assert queries.count("Ly hôn") == 1
    assert "Ly hôn đơn phương" in queries


def test_expand_query_falls_back_to_original_on_invalid_json() -> None:
    with patch("services.multi_query._run_pooled", return_value="not json"):
        queries = expand_query("Ly hôn", n_variants=2)
    assert queries == ["Ly hôn"]


def test_expand_query_falls_back_on_empty_response() -> None:
    with patch("services.multi_query._run_pooled", return_value=""):
        queries = expand_query("Ly hôn", n_variants=2)
    assert queries == ["Ly hôn"]
```

Ghi `backend/tests/services/test_crossref_walker.py`:

```python
from unittest.mock import patch

from services.crossref_walker import walk_relationships


def test_walk_relationships_returns_related_chunks() -> None:
    seeds = [
        {"id": "1", "content_text": "Điều 51", "relationships": [{"target_id": "2"}, {"target_id": "3"}]},
    ]
    fetched = [
        {"id": "2", "content_text": "Nghị định 126", "title": "NĐ 126"},
        {"id": "3", "content_text": "Thông tư 01", "title": "TT 01"},
    ]
    with patch("services.crossref_walker._fetch_by_ids", return_value=fetched):
        results = walk_relationships(seeds, max_hops=1, max_chunks=5)
    ids = [r["id"] for r in results]
    assert "2" in ids and "3" in ids
    assert all("score" in r for r in results)


def test_walk_relationships_dedupes_against_seeds() -> None:
    seeds = [
        {"id": "1", "content_text": "A", "relationships": [{"target_id": "1"}, {"target_id": "2"}]},
    ]
    fetched = [{"id": "2", "content_text": "B"}]
    with patch("services.crossref_walker._fetch_by_ids", return_value=fetched):
        results = walk_relationships(seeds, max_chops=1, max_chunks=5)
    ids = [r["id"] for r in results]
    assert "1" not in ids
    assert "2" in ids


def test_walk_relationships_caps_at_max_chunks() -> None:
    seeds = [{"id": "1", "content_text": "A", "relationships": [{"target_id": str(i)} for i in range(10)]}]
    fetched = [{"id": str(i), "content_text": f"d{i}"} for i in range(10)]
    with patch("services.crossref_walker._fetch_by_ids", return_value=fetched):
        results = walk_relationships(seeds, max_hops=1, max_chunks=3)
    assert len(results) == 3
```

- [ ] **Step 5: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_hybrid_search.py tests/services/test_multi_query.py tests/services/test_crossref_walker.py -v
```

Expected: 4 + 4 + 3 = 11 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/hybrid_search.py backend/services/multi_query.py backend/services/crossref_walker.py backend/prompts/multi_query_v1.md \
        backend/tests/services/test_hybrid_search.py backend/tests/services/test_multi_query.py backend/tests/services/test_crossref_walker.py
git commit -m "feat(retrieval): hybrid BM25+vector + multi-query + crossref walker"
```

---

## Task 3.3: Citation verifier

**Files:**
- Create: `backend/services/citation_verifier.py`
- Test: `backend/tests/services/test_citation_verifier.py`

- [ ] **Step 1: Tạo service**

Ghi `backend/services/citation_verifier.py`:

```python
"""Verify LLM-cited chunk IDs against retrieved chunks; drop unverifiable ones."""
import logging
import re
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

# Citation strings LLM might produce
_CITATION_RE = re.compile(
    r"(Điều\s+\d+[^,;\n]*)|(Khoản\s+\d+[^,;\n]*)|(Điểm\s+[a-z]\d*[^,;\n]*)",
    re.IGNORECASE,
)


def _extract_citation_phrases(text: str) -> set[str]:
    """Extract likely citation phrases from a piece of text."""
    return {m.group(0).strip().lower() for m in _CITATION_RE.finditer(text or "")}


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _phrase_present_in_chunks(phrase: str, chunks: list[dict]) -> bool:
    """A citation phrase is 'verified' if it appears (fuzzy ≥ 0.8) in any chunk content."""
    for c in chunks:
        content = (c.get("content_text") or "").lower()
        if phrase in content:
            return True
        # Fuzzy: look for the most similar substring of length >= len(phrase)//2
        if len(phrase) >= 5 and _similarity(phrase[:30], content[:300]) >= 0.8:
            return True
    return False


def verify_citations(
    structured: dict,
    contexts: list[dict[str, Any]],
) -> dict:
    """Filter structured['trich_dan_nguon'] to only include verifiable ones.

    Also augments structured['trich_dan_nguon'] with source_url from matching
    context for any verified citation.

    Returns the (mutated) structured dict.
    """
    cited: list[str] = structured.get("trich_dan_nguon") or []
    if not cited:
        return structured
    verified: list[str] = []
    dropped: list[str] = []
    for cite in cited:
        phrases = _extract_citation_phrases(cite)
        # If no recognizable citation phrase, just trust the cite as-is
        if not phrases:
            verified.append(cite)
            continue
        if any(_phrase_present_in_chunks(p, contexts) for p in phrases):
            verified.append(cite)
        else:
            dropped.append(cite)
            logger.info("Citation dropped (no matching chunk): %r", cite)
    structured["trich_dan_nguon"] = verified
    if dropped:
        logger.info("verify_citations: kept %d, dropped %d", len(verified), len(dropped))
    return structured
```

- [ ] **Step 2: Viết failing test**

Ghi `backend/tests/services/test_citation_verifier.py`:

```python
from services.citation_verifier import (
    _extract_citation_phrases,
    _phrase_present_in_chunks,
    verify_citations,
)


def test_extract_citation_phrases_finds_dieu_and_khoan() -> None:
    text = "Căn cứ Điều 51 Khoản 2 Luật HNGĐ và Điểm a Khoản 1 Điều 56"
    phrases = _extract_citation_phrases(text)
    joined = " ".join(phrases)
    assert "điều 51" in joined
    assert "khoản 2" in joined
    assert "điểm a" in joined


def test_phrase_present_in_chunks_exact_match() -> None:
    chunks = [{"content_text": "Điều 51 quy định về quyền yêu cầu ly hôn"}]
    assert _phrase_present_in_chunks("điều 51", chunks) is True


def test_phrase_present_in_chunks_miss() -> None:
    chunks = [{"content_text": "Điều 56 thuận tình ly hôn"}]
    assert _phrase_present_in_chunks("điều 51", chunks) is False


def test_verify_citations_drops_unverifiable() -> None:
    structured = {
        "trich_dan_nguon": [
            "Điều 51 - Luật HNGĐ",
            "Điều 999 - Luật XYZ",  # fabricated
        ],
    }
    contexts = [
        {"content_text": "Điều 51 quy định về quyền yêu cầu ly hôn"},
    ]
    result = verify_citations(structured, contexts)
    assert "Điều 51 - Luật HNGĐ" in result["trich_dan_nguon"]
    assert "Điều 999 - Luật XYZ" not in result["trich_dan_nguon"]


def test_verify_citations_keeps_non_phrase_citations() -> None:
    structured = {"trich_dan_nguon": ["https://example.com/luat-hngd"]}
    contexts = []
    result = verify_citations(structured, contexts)
    assert result["trich_dan_nguon"] == ["https://example.com/luat-hngd"]


def test_verify_citations_empty_input_returns_unchanged() -> None:
    structured = {"trich_dan_nguon": []}
    contexts = [{"content_text": "anything"}]
    result = verify_citations(structured, contexts)
    assert result == {"trich_dan_nguon": []}
```

- [ ] **Step 3: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_citation_verifier.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/services/citation_verifier.py backend/tests/services/test_citation_verifier.py
git commit -m "feat(verify): drop LLM-fabricated citations not in retrieved chunks"
```

---

## Task 3.4: Wire hybrid + multi-query + crossref + verify vào chat_service

**Files:**
- Modify: `backend/services/chat_service.py` (rewrite retrieval + post-process)
- Test: `backend/tests/services/test_chat_service.py` (extend)

- [ ] **Step 1: Viết failing test cho Sprint 3 wiring**

Sửa `backend/tests/services/test_chat_service.py` — thêm 3 test cuối file:

```python
def test_chat_uses_hybrid_search_instead_of_pure_vector(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])
    class FakeS:
        case_type = None
        case_summary = None
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeS())

    captured = {}
    def fake_hybrid(query, **kwargs):
        captured["query"] = query
        return [{"id": "1", "content_text": "Điều 51", "title": "Luật HNGĐ", "source_url": "u", "score": 0.9}]

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(chat_service, "multi_query_expand", lambda q, n: [q])
    monkeypatch.setattr(chat_service, "walk_relationships", lambda chunks, **_: [])
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào", "tom_tat_vu_viec": "ok", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok",
                "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"]
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None, "updated_case_summary": None,
        },
    )
    monkeypatch.setattr(chat_service, "verify_citations",
        lambda s, c: s)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="ly hôn đơn phương")
    assert captured["query"] == "ly hôn đơn phương"


def test_chat_merges_hybrid_and_crossref_contexts(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])
    class FakeS:
        case_type = None
        case_summary = None
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeS())

    hybrid = [{"id": "1", "content_text": "Điều 51", "title": "L", "source_url": "u", "score": 0.9}]
    crossref = [{"id": "2", "content_text": "Nghị định 126 hướng dẫn Điều 51", "title": "NĐ 126", "source_url": "v", "score": 0.0}]

    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: hybrid)
    monkeypatch.setattr(chat_service, "multi_query_expand", lambda q, n: [q])
    monkeypatch.setattr(chat_service, "walk_relationships", lambda *_, **__: crossref)

    captured = {}
    def fake_two_stage(**kwargs):
        captured["context_ids"] = [c.get("id") for c in kwargs["contexts"]]
        return {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None, "updated_case_summary": None,
        }
    monkeypatch.setattr(chat_service, "two_stage_reason", fake_two_stage)
    monkeypatch.setattr(chat_service, "verify_citations", lambda s, c: s)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="q")
    assert "1" in captured["context_ids"]
    assert "2" in captured["context_ids"]


def test_chat_verifies_citations_before_persisting(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])
    class FakeS:
        case_type = None
        case_summary = None
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeS())
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "multi_query_expand", lambda q, n: [q])
    monkeypatch.setattr(chat_service, "walk_relationships", lambda *_, **__: [])

    captured = {}
    def fake_verify(structured, contexts):
        # Simulate verifier dropping one citation
        structured["trich_dan_nguon"] = ["Điều 51 - Luật HNGĐ"]
        captured["called"] = True
        return structured
    monkeypatch.setattr(chat_service, "verify_citations", fake_verify)

    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok",
                "trich_dan_nguon": ["Điều 51 - Luật HNGĐ", "Điều 999 - Fabricated"]
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None, "updated_case_summary": None,
        },
    )
    saved = {}
    def fake_save(db, *args, **kwargs):
        saved["structured"] = kwargs.get("sources_json", {}).get("structured")
        return object()
    monkeypatch.setattr(chat_service, "save_message", fake_save)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="q")
    assert captured["called"] is True
    assert "Điều 999" not in saved["structured"]["trich_dan_nguon"]
```

- [ ] **Step 2: Chạy test, confirm fail**

```bash
cd backend
pytest tests/services/test_chat_service.py -v
```

Expected: 3 new tests FAIL (chat_service vẫn dùng `search_legal_context` cũ, chưa gọi `verify_citations`).

- [ ] **Step 3: Sửa chat_service.py — thay retrieval pipeline**

Ghi đè `backend/services/chat_service.py`:

```python
import logging

from services.crossref_walker import walk_relationships
from services.hybrid_search import hybrid_search
from services.multi_query import expand_query as multi_query_expand
from services.citation_verifier import verify_citations
from services.session_service import (
    add_fact,
    get_session,
    list_case_facts,
    save_message,
    update_session_case,
)
from services.two_stage_reasoner import two_stage_reason
from repositories.messages import list_recent_messages
from core.config import MULTI_QUERY_COUNT, RETRIEVAL_TOP_K

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
LOW_SCORE_THRESHOLD = 0.30  # hybrid scores are normalized 0-1, so 0.30 is low


def _format_history_for_llm(messages) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _structured_to_display_text(structured: dict) -> str:
    parts: list[str] = []
    if structured.get("loi_chao"):
        parts.append(f"**{structured['loi_chao']}**\n")
    if structured.get("tom_tat_vu_viec"):
        parts.append(f"### Tóm tắt vụ việc\n{structured['tom_tat_vu_viec']}\n")
    if structured.get("phan_tich_phap_ly"):
        parts.append(f"### Phân tích pháp lý\n{structured['phan_tich_phap_ly']}\n")
    if structured.get("phuong_an_khuyen_nghi"):
        parts.append("### Phương án khuyến nghị")
        parts.extend(f"- {p}" for p in structured["phuong_an_khuyen_nghi"])
        parts.append("")
    if structured.get("rui_ro_can_luu_y"):
        parts.append("### Rủi ro cần lưu ý")
        parts.extend(f"- {r}" for r in structured["rui_ro_can_luu_y"])
        parts.append("")
    if structured.get("cau_hoi_hoi_them"):
        parts.append("### Câu hỏi cần bạn cung cấp thêm")
        parts.extend(f"- {c}" for c in structured["cau_hoi_hoi_them"])
        parts.append("")
    if structured.get("disclaimer"):
        parts.append(f"> ⚠️ {structured['disclaimer']}")
    return "\n".join(parts).strip()


def _is_retrieval_reliable(contexts: list[dict]) -> bool:
    if not contexts:
        return False
    if any(c.get("score", 1.0) < LOW_SCORE_THRESHOLD for c in contexts):
        return False
    return True


def _multi_query_retrieve(
    message: str,
    filters: dict | None,
    top_k: int,
) -> list[dict]:
    """Run multi-query expansion + hybrid search, then dedupe and merge."""
    queries = multi_query_expand(message, n_variants=MULTI_QUERY_COUNT)
    logger.info("multi_query: %d variants for session", len(queries))
    seen: dict[str, dict] = {}
    for q in queries:
        for chunk in hybrid_search(q, filters=filters, top_k=top_k):
            cid = chunk.get("id") or chunk.get("doc_id")
            if cid is None:
                continue
            if cid not in seen or chunk.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = chunk
    merged = list(seen.values())
    merged.sort(key=lambda c: c.get("score", 0), reverse=True)
    return merged[:top_k]


def _persist_extracted_facts(db, session_id, user_id, source_message_id, extracted):
    for fact in extracted.get("extracted_facts", []) or []:
        if not fact.get("key") or fact.get("value") is None:
            continue
        add_fact(
            db,
            session_id=session_id,
            user_id=user_id,
            fact_key=fact["key"],
            fact_value=str(fact["value"]),
            source_message_id=source_message_id,
            confidence=float(fact.get("confidence", 1.0)),
        )


def _persist_case_update(db, session_id, user_id, case_type, case_summary, *, mark_intake_complete=False):
    from datetime import datetime
    update_session_case(
        db, session_id=session_id, user_id=user_id,
        case_type=case_type, case_summary=case_summary,
        conversation_phase="consulting" if mark_intake_complete else None,
        intake_completed_at=datetime.utcnow() if mark_intake_complete else None,
    )


def send_chat_message(db, session_id, user_id, message) -> tuple[str, list[str], dict | None, dict | None]:
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    user_msg = save_message(db, session_id, user_id, "user", message)

    recent = list_recent_messages(db, session_id, limit=HISTORY_LIMIT)
    history = _format_history_for_llm(recent[:-1])

    existing_facts = list_case_facts(db, session_id)

    # SPRINT 3: hybrid + multi-query retrieval
    contexts = _multi_query_retrieve(message, filters=None, top_k=RETRIEVAL_TOP_K)

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

    if not _is_retrieval_reliable(contexts):
        logger.info("Retrieval unreliable for session=%s", session_id)

    try:
        result = two_stage_reason(
            message=message, contexts=contexts, history=history,
            existing_facts=existing_facts,
            case_type=getattr(session, "case_type", None),
            case_summary=getattr(session, "case_summary", None),
        )
    except ValueError as exc:
        logger.warning("Two-stage failed: %s", exc)
        from services.groq_service import generate_answer
        text = generate_answer(question=message, contexts=contexts, history=history)
        save_message(db, session_id, user_id, "assistant", text, {"sources": []})
        return text, [], None, None

    structured = result["structured"]

    # SPRINT 3: verify citations against retrieved contexts
    structured = verify_citations(structured, contexts)

    _persist_extracted_facts(db, session_id, user_id, user_msg.id, result["extracted"])
    _persist_case_update(
        db, session_id, user_id,
        case_type=result.get("updated_case_type"),
        case_summary=result.get("updated_case_summary"),
        mark_intake_complete=bool(result["extracted"].get("extracted_facts")),
    )

    display = _structured_to_display_text(structured)
    sources = [c.get("source_url", "") for c in contexts if c.get("source_url")]
    case_brief = {
        "case_type": result.get("updated_case_type"),
        "case_summary": result.get("updated_case_summary"),
        "facts": [{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in existing_facts],
    }
    save_message(
        db, session_id, user_id, "assistant", display,
        {"sources": sources, "structured": structured, "case_brief": case_brief},
    )
    return display, sources, structured, case_brief
```

> **Lưu ý:** Thêm `RETRIEVAL_TOP_K` vào `core/config.py` nếu chưa có (Task 1.4 dùng hard-coded 4, giờ chuyển sang config):

Sửa `backend/core/config.py` — thêm:

```python
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "8"))
```

- [ ] **Step 4: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/ -v
```

Expected: tất cả PASS (test_chat_service 7 Sprint 1-2 + 3 Sprint 3 = 10).

- [ ] **Step 5: Commit**

```bash
git add backend/services/chat_service.py backend/core/config.py backend/tests/services/test_chat_service.py
git commit -m "feat(chat): wire hybrid retrieval + crossref + citation verify"
```

---

## Task 3.5: Build BM25 index script + auto-build on backend startup

**Files:**
- Create: `backend/scripts/build_bm25_index.py`
- Modify: `backend/main.py` (build on startup if missing)
- Test: smoke

- [ ] **Step 1: Tạo CLI script**

Ghi `backend/scripts/build_bm25_index.py`:

```python
"""Build (or rebuild) the BM25 index from the current Qdrant collection.

Usage:
    python -m scripts.build_bm25_index
    python -m scripts.build_bm25_index --output /custom/path.pkl
"""
import argparse
import logging

from services.bm25_index import build_index, save_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", default=None, help="Override BM25_INDEX_PATH")
    args = parser.parse_args()

    logger.info("Building BM25 index...")
    bm25, meta = build_index()
    save_index(bm25, meta, args.output)
    logger.info("Done. Indexed %d documents.", len(meta))


if __name__ == "__main__":
    main()
```

Đảm bảo `backend/scripts/__init__.py` tồn tại (rỗng).

- [ ] **Step 2: Build index lần đầu**

```bash
cd backend
python -m scripts.build_bm25_index
ls -lh data/bm25_index.pkl
```

Expected: file `data/bm25_index.pkl` tồn tại, size > 0.

- [ ] **Step 3: Auto-build on backend startup nếu index missing**

Sửa `backend/main.py` (file hiện có — đọc trước khi sửa). Tìm đoạn startup, thêm:

```python
import logging
from contextlib import asynccontextmanager
from services.bm25_index import build_index, load_index, save_index

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    # Build BM25 index on startup if missing
    try:
        if load_index() is None:
            logger.info("BM25 index not found, building...")
            bm25, meta = build_index()
            save_index(bm25, meta)
            logger.info("BM25 index built with %d docs", len(meta))
    except Exception as exc:
        logger.warning("BM25 index build failed (continuing without it): %s", exc)
    yield
```

Sửa `app = FastAPI(...)` thành:

```python
app = FastAPI(lifespan=lifespan)
```

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/build_bm25_index.py backend/scripts/__init__.py backend/main.py
git commit -m "feat(bm25): CLI builder + auto-build on backend startup"
```

---

## Task 3.6: Frontend — LegalCitationChip, SuggestedFollowUps, DisclaimerBanner

**Files:**
- Create: `frontend/components/chat/legal-citation-chip.tsx`
- Create: `frontend/components/chat/suggested-follow-ups.tsx`
- Create: `frontend/components/chat/disclaimer-banner.tsx`
- Modify: `frontend/components/chat/assistant-message.tsx` (use new components)
- Modify: `frontend/components/chat/lawyer-response-view.tsx` (use chips + follow-ups)
- Modify: `frontend/app/chat/[sessionId]/page.tsx` (mount banner)

- [ ] **Step 1: Tạo LegalCitationChip**

Ghi `frontend/components/chat/legal-citation-chip.tsx`:

```tsx
'use client'

import { useState } from 'react'

interface LegalCitationChipProps {
  citation: string
  sourceUrl?: string
}

const ARTICLE_RE = /(Điều\s+\d+[^,;\n]*?)(?=,|$|;|\n|Khoản|Điểm)/i
const KHOAN_RE = /Khoản\s+\d+/i
const DIEM_RE = /Điểm\s+[a-z]\d*/i

export function parseCitation(citation: string): { article?: string; khoan?: string; diem?: string; raw: string } {
  const articleMatch = citation.match(ARTICLE_RE)
  const khoanMatch = citation.match(KHOAN_RE)
  const diemMatch = citation.match(DIEM_RE)
  return {
    article: articleMatch?.[1]?.trim(),
    khoan: khoanMatch?.[0]?.trim(),
    diem: diemMatch?.[0]?.trim(),
    raw: citation,
  }
}

export function LegalCitationChip({ citation, sourceUrl }: LegalCitationChipProps) {
  const [expanded, setExpanded] = useState(false)
  const parsed = parseCitation(citation)
  const label = [parsed.diem, parsed.khoan, parsed.article].filter(Boolean).join(' · ') || citation

  return (
    <span className="legal-citation-chip" role="button" tabIndex={0}
      onClick={() => setExpanded((v) => !v)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v) }}
      aria-expanded={expanded}
      aria-label={`Trích dẫn: ${citation}`}
    >
      <span className="legal-citation-label">📜 {label}</span>
      {expanded && (
        <span className="legal-citation-detail" role="tooltip">
          {sourceUrl ? (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
              Mở văn bản gốc ↗
            </a>
          ) : (
            <em>Không có link nguồn</em>
          )}
        </span>
      )}
    </span>
  )
}
```

- [ ] **Step 2: Tạo SuggestedFollowUps**

Ghi `frontend/components/chat/suggested-follow-ups.tsx`:

```tsx
'use client'

interface SuggestedFollowUpsProps {
  questions: string[]
  onSelect: (question: string) => void
}

export function SuggestedFollowUps({ questions, onSelect }: SuggestedFollowUpsProps) {
  if (!questions.length) return null
  return (
    <div className="suggested-follow-ups" aria-label="Câu hỏi gợi ý tiếp theo">
      <p className="follow-ups-label">Có thể bạn muốn hỏi tiếp:</p>
      <ul>
        {questions.map((q, i) => (
          <li key={i}>
            <button type="button" className="follow-up-chip" onClick={() => onSelect(q)}>
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 3: Tạo DisclaimerBanner**

Ghi `frontend/components/chat/disclaimer-banner.tsx`:

```tsx
'use client'

import { useState } from 'react'

export function DisclaimerBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return (
    <aside className="disclaimer-banner" role="alert">
      <p>
        ⚠️ <strong>Lưu ý:</strong> Nội dung tư vấn mang tính tham khảo, dựa trên cơ sở dữ liệu
        văn bản pháp luật hiện có. Không thay thế ý kiến luật sư hành nghề cho hồ sơ cụ thể
        của bạn. Vụ việc phức tạp nên liên hệ Luật sư đoàn tại địa phương.
      </p>
      <button type="button" onClick={() => setDismissed(true)} aria-label="Đóng cảnh báo">
        ✕
      </button>
    </aside>
  )
}
```

- [ ] **Step 4: Sửa LawyerResponseView dùng chip + follow-ups**

Sửa `frontend/components/chat/lawyer-response-view.tsx`:

```tsx
'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { LawyerSection } from '@/lib/api'
import { LegalCitationChip } from './legal-citation-chip'
import { SuggestedFollowUps } from './suggested-follow-ups'

interface LawyerResponseViewProps {
  section: LawyerSection
  sources: string[] | undefined
  onSelectFollowUp?: (q: string) => void
}

export function LawyerResponseView({ section, sources, onSelectFollowUp }: LawyerResponseViewProps) {
  const hasAny =
    section.loi_chao ||
    section.tom_tat_vu_viec ||
    section.phan_tich_phap_ly ||
    section.phuong_an_khuyen_nghi.length > 0 ||
    section.rui_ro_can_luu_y.length > 0 ||
    section.cau_hoi_hoi_them.length > 0

  if (!hasAny) return null

  return (
    <div className="lawyer-response" data-testid="lawyer-response">
      {section.loi_chao && (
        <p className="lawyer-greeting" role="doc-subtitle">{section.loi_chao}</p>
      )}

      {section.tom_tat_vu_viec && (
        <section aria-label="Tóm tắt vụ việc">
          <h4>Tóm tắt vụ việc</h4>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.tom_tat_vu_viec}</ReactMarkdown>
        </section>
      )}

      {section.phan_tich_phap_ly && (
        <section aria-label="Phân tích pháp lý">
          <h4>Phân tích pháp lý</h4>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.phan_tich_phap_ly}</ReactMarkdown>
        </section>
      )}

      {section.phuong_an_khuyen_nghi.length > 0 && (
        <section aria-label="Phương án khuyến nghị">
          <h4>Phương án khuyến nghị</h4>
          <ul>
            {section.phuong_an_khuyen_nghi.map((p, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{p}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.rui_ro_can_luu_y.length > 0 && (
        <section aria-label="Rủi ro cần lưu ý" className="lawyer-warn-block">
          <h4>⚠️ Rủi ro cần lưu ý</h4>
          <ul>
            {section.rui_ro_can_luu_y.map((r, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{r}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.cau_hoi_hoi_them.length > 0 && onSelectFollowUp && (
        <SuggestedFollowUps questions={section.cau_hoi_hoi_them} onSelect={onSelectFollowUp} />
      )}

      {section.disclaimer && (
        <aside className="lawyer-disclaimer" role="note">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.disclaimer}</ReactMarkdown>
        </aside>
      )}

      {section.trich_dan_nguon.length > 0 && (
        <div className="legal-citations" aria-label="Trích dẫn pháp lý">
          {section.trich_dan_nguon.map((cite, i) => (
            <LegalCitationChip key={i} citation={cite} sourceUrl={sources?.[i]} />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Sửa AssistantMessage nhận onSelectFollowUp**

Sửa `frontend/components/chat/assistant-message.tsx`:

```tsx
'use client'

import { LawyerResponseView } from './lawyer-response-view'
import type { ChatUiMessage } from './chat.types'

interface AssistantMessageProps {
  message: ChatUiMessage
  onCopy: (text: string) => void
  onSelectFollowUp?: (q: string) => void
}

export function AssistantMessage({ message, onCopy, onSelectFollowUp }: AssistantMessageProps) {
  const hasStructured =
    message.structured &&
    (message.structured.loi_chao ||
      message.structured.tom_tat_vu_viec ||
      message.structured.phan_tich_phap_ly)

  return (
    <article className="message-row">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        Lx
      </div>
      <div className="message-card message-card--assistant">
        {hasStructured && message.structured ? (
          <LawyerResponseView
            section={message.structured}
            sources={message.sources}
            onSelectFollowUp={onSelectFollowUp}
          />
        ) : (
          <pre className="message-fallback-text">{message.content}</pre>
        )}

        <div className="message-actions">
          <button
            type="button"
            className="message-action"
            onClick={() => onCopy(message.content)}
            title="Sao chép nội dung"
          >
            Sao chép
          </button>
        </div>
      </div>
    </article>
  )
}
```

- [ ] **Step 6: Mount DisclaimerBanner trong chat page**

Sửa `frontend/app/chat/[sessionId]/page.tsx` — thêm import và render:

```tsx
import { DisclaimerBanner } from '@/components/chat/disclaimer-banner'

// ... existing imports ...

return (
  <main>
    <DisclaimerBanner />
    {/* ... rest of existing chat UI ... */}
  </main>
)
```

Wire `onSelectFollowUp` ở nơi dùng `AssistantMessage`:

```tsx
<AssistantMessage
  message={msg}
  onCopy={handleCopy}
  onSelectFollowUp={(q) => {
    setComposerValue(q)
    composerRef.current?.focus()
  }}
/>
```

> **Lưu ý:** `composerRef` và `setComposerValue` là state hiện có của chat page — đọc file trước khi sửa để biết tên chính xác.

- [ ] **Step 7: Smoke test thủ công**

```bash
cd backend
pytest -v
cd ..
# Build BM25 index
cd backend && python -m scripts.build_bm25_index
# Run backend
uvicorn main:app --reload
# Frontend
cd frontend && npm run dev
```

Test:
1. Mở chat page → **DisclaimerBanner hiển thị đầu trang**, có nút ✕ để đóng.
2. Hỏi "Điều kiện đơn phương ly hôn?" → response có citation chip "📜 Điều 51 · Khoản 1".
3. Click chip → expand ra link "Mở văn bản gốc ↗".
4. Nếu response có `cau_hoi_hoi_them` → hiển thị SuggestedFollowUps.
5. Click 1 follow-up → composer được fill với câu đó.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/chat/legal-citation-chip.tsx \
        frontend/components/chat/suggested-follow-ups.tsx \
        frontend/components/chat/disclaimer-banner.tsx \
        frontend/components/chat/assistant-message.tsx \
        frontend/components/chat/lawyer-response-view.tsx \
        frontend/app/chat/
git commit -m "feat(ui): citation chip + suggested follow-ups + disclaimer banner"
```

---

## Task 3.7: End-to-end integration test (Sprint 3)

**Files:**
- Create: `backend/tests/api/test_chat_endpoint_sprint3.py`
- Test: smoke via test client

- [ ] **Step 1: Tạo integration test**

Ghi `backend/tests/api/test_chat_endpoint_sprint3.py`:

```python
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_chat_endpoint_returns_verified_citations_and_follow_ups(client, monkeypatch):
    """End-to-end: chat endpoint with all Sprint 3 features wired."""
    # Pre-create user + session
    from db.init_db import init_db
    from entities.user import User
    from entities.chat_session import ChatSession
    from db.session import SessionLocal
    from services.auth_service import create_access_token
    from uuid import uuid4

    db = SessionLocal()
    try:
        u = User(id=str(uuid4()), email="e2e@test.c", password_hash="x")
        db.add(u)
        db.commit()
        sid = str(uuid4())
        s = ChatSession(id=sid, user_id=u.id, title="e2e")
        db.add(s)
        db.commit()
        token = create_access_token({"sub": u.id})
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {token}"}

    with patch("services.chat_service.hybrid_search", return_value=[
        {"id": "1", "content_text": "Điều 51 quy định về quyền yêu cầu ly hôn đơn phương",
         "title": "Luật HNGĐ 2014", "source_url": "https://example/51", "score": 0.9}
    ]), \
         patch("services.chat_service.multi_query_expand", return_value=["x"]), \
         patch("services.chat_service.walk_relationships", return_value=[]), \
         patch("services.chat_service.verify_citations", side_effect=lambda s, c: s), \
         patch("services.chat_service.two_stage_reason", return_value={
             "structured": {
                 "loi_chao": "Chào", "tom_tat_vu_viec": "Ly hôn",
                 "phan_tich_phap_ly": "Điều 51 quy định...",
                 "phuong_an_khuyen_nghi": ["Thỏa thuận"],
                 "rui_ro_can_luu_y": ["Thời hiệu 2 năm"],
                 "cau_hoi_hoi_them": ["Bạn có con chung không?"],
                 "disclaimer": "ok",
                 "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"]
             },
             "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
             "updated_case_type": None, "updated_case_summary": None,
         }):
        resp = await client.post(
            "/chat",
            json={"session_id": sid, "message": "ly hôn đơn phương"},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "Điều 51" in data["reply"]
    assert data["structured"]["trich_dan_nguon"] == ["Điều 51 - Luật HNGĐ"]
    assert data["sources"] == ["https://example/51"]
    assert data["case_brief"] is not None
```

- [ ] **Step 2: Đảm bảo fixtures cần thiết**

Nếu `db/init_db.py` chưa tồn tại: kiểm tra; nếu `services/auth_service.py` chưa tồn tại: check tên thật qua grep.

- [ ] **Step 3: Chạy test, confirm pass**

```bash
cd backend
pytest tests/api/test_chat_endpoint_sprint3.py -v
```

Expected: 1 test PASS (hoặc skip nếu auth flow phức tạp — doc lại trong commit message).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/api/test_chat_endpoint_sprint3.py
git commit -m "test(e2e): chat endpoint with hybrid retrieval + verified citations"
```

---

## Self-review Sprint 3

- [ ] Tất cả test pass: `cd backend && pytest -v` — 37 (Sprint 1+2) + 4 bm25 + 11 hybrid/multi/crossref + 6 verify + 3 chat wiring + 1 e2e = **62 tests**.
- [ ] BM25 index build thành công trên Neon dev Qdrant: `python -m scripts.build_bm25_index`.
- [ ] Citation verifier drop đúng citation fabricated trong test.
- [ ] Suggested follow-ups render khi `cau_hoi_hoi_them` không rỗng.
- [ ] DisclaimerBanner có thể đóng (state local).
- [ ] File `bm25_index.py`, `hybrid_search.py`, `crossref_walker.py` mỗi file < 250 dòng.
- [ ] Không regression Sprint 1+2: persona, intake, case_facts vẫn hoạt động.

---

## Kết thúc Sprint 3 — Done toàn bộ roadmap

Sau Sprint 3, hệ thống đáp ứng **~5/5** yêu cầu luật sư thật thụ:

| Yêu cầu | Sprint đảm nhận | Demo được |
|---|---|---|
| Hỏi thêm khi thiếu facts | 1 (cau_hoi_hoi_them trong structured) + 2 (intake form) | ✅ |
| Phân loại quan hệ pháp luật | 2 (case_type + case_summary) | ✅ |
| Tra cứu cơ sở pháp lý | 3 (hybrid BM25 + vector) | ✅ |
| Phân tích điều luật | 3 (cross-ref walker + citation verify) | ✅ |
| Khuyến nghị + rủi ro | 1 (phuong_an_khuyen_nghi + rui_ro_can_luu_y) | ✅ |
| Trích dẫn chính xác | 3 (LegalCitationChip + verify) | ✅ |
| Nhớ case qua nhiều lượt | 2 (case_facts + case_brief) | ✅ |
| Disclaimer chuyên nghiệp | 1 (trong response) + 3 (banner cố định) | ✅ |
| UX chuyên nghiệp | 3 (chip, follow-ups, banner) | ✅ |

**Effort tổng thực tế** (ước tính): ~5-6 ngày làm việc thực (3 sprint, có test + commit đầy đủ).

**Next step gợi ý (out of scope):** Sprint 4 — Streaming SSE, prompt A/B testing framework, multi-user collaborative sessions, voice input.
