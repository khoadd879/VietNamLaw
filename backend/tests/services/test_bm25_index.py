from unittest.mock import MagicMock, patch
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
                FakePoint("1", {"content_text": "Điều 51 quyền yêu cầu ly hôn", "article_title": "Điều 51 - Luật HNGĐ", "source_url": "https://phapdien/51"}),
                FakePoint("2", {"content_text": "Điều 56 thuận tình ly hôn", "article_title": "Điều 56 - Luật HNGĐ", "source_url": "https://phapdien/56"}),
            ], None
    import services.bm25_index as mod
    mod.get_qdrant_client = lambda: FakeClient()
    bm25, meta = build_index()
    assert isinstance(bm25, BM25Okapi)
    assert len(meta) == 2
    assert meta[0]["content_text"].startswith("Điều 51")
    assert meta[0]["title"] == "Điều 51 - Luật HNGĐ"


def test_scroll_all_points_returns_5_field_shape() -> None:
    from services.bm25_index import _scroll_all_points

    fake_point = MagicMock()
    fake_point.id = "point-uuid"
    fake_point.payload = {
        "content_text": "Nội dung điều luật",
        "article_title": "Điều 1. Phạm vi",
        "source_url": "https://phapdien.moj.gov.vn/x",
        "chapter_title": "Chương I",
        "subject_title": "An ninh quốc gia",
        "scraped_at": "2026-05-08",
    }

    with patch("services.bm25_index.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.scroll.return_value = ([fake_point], None)
        mock_get_client.return_value = mock_client
        docs = list(_scroll_all_points())

    assert len(docs) == 1
    assert set(docs[0].keys()) == {"id", "content_text", "title", "source_url"}
    assert docs[0]["title"] == "Điều 1. Phạm vi"


def test_search_returns_relevant_docs_in_order() -> None:
    class FakeClient:
        def scroll(self, **kwargs):
            class P:
                def __init__(self, i, t, title):
                    self.id = i
                    self.payload = {"content_text": t, "article_title": title, "source_url": "https://x/y"}
            return [
                P(1, "Điều 51 quyền yêu cầu ly hôn", "Điều 51 - Luật HNGĐ"),
                P(2, "Điều 56 thuận tình ly hôn", "Điều 56 - Luật HNGĐ"),
            ], None
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
                    self.payload = {"content_text": t, "article_title": "T", "source_url": "https://x"}
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
