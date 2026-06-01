from unittest.mock import patch

from services.crossref_walker import walk_relationships


def test_walk_relationships_returns_related_chunks() -> None:
    seeds = [
        {"id": "1", "content_text": "Điều 51", "relationships": [{"target_id": "2"}, {"target_id": "3"}]},
    ]
    fetched = [
        {"id": "2", "content_text": "Nghị định 126", "title": "NĐ 126", "score": 0.0},
        {"id": "3", "content_text": "Thông tư 01", "title": "TT 01", "score": 0.0},
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
        results = walk_relationships(seeds, max_hops=1, max_chunks=5)
    ids = [r["id"] for r in results]
    assert "1" not in ids
    assert "2" in ids


def test_walk_relationships_caps_at_max_chunks() -> None:
    seeds = [{"id": "1", "content_text": "A", "relationships": [{"target_id": str(i)} for i in range(10)]}]
    fetched = [{"id": str(i), "content_text": f"d{i}", "score": 0.0} for i in range(10)]
    with patch("services.crossref_walker._fetch_by_ids", return_value=fetched):
        results = walk_relationships(seeds, max_hops=1, max_chunks=3)
    assert len(results) == 3