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