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
        {"id": "2", "content_text": "B", "score": 0.9},
        {"id": "1", "content_text": "A", "score": 0.5},
    ]
    bm25_results = [
        {"id": "2", "content_text": "B", "bm25_score": 2.5},
        {"id": "3", "content_text": "C", "bm25_score": 1.0},
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