from unittest.mock import MagicMock, patch

from uuid import NAMESPACE_URL, uuid5


class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._json


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, json: dict) -> FakeResponse:
        self.calls.append({"url": url, "json": json})
        if not self._responses:
            raise AssertionError("no fake responses left")
        return self._responses.pop(0)


def make_embed_response(values: list[float]) -> FakeResponse:
    return FakeResponse({"embeddings": [values]})


# ─── embed_texts tests (kept, unchanged) ───────────────────────────────────────

def test_embed_texts_calls_ollama_with_configured_model() -> None:
    from services.qdrant_service import embed_texts

    fake_client = FakeHttpClient([make_embed_response([0.1] * 1024)])

    with patch("services.qdrant_service.httpx.Client", return_value=fake_client):
        with patch("services.qdrant_service.OLLAMA_URL", "http://localhost:11434"):
            with patch("services.qdrant_service.OLLAMA_EMBEDDING_MODEL", "bge-m3"):
                vectors = embed_texts(["Điều kiện ly hôn đơn phương"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 1024
    assert fake_client.calls[0]["url"] == "http://localhost:11434/api/embed"
    assert fake_client.calls[0]["json"]["model"] == "bge-m3"
    assert fake_client.calls[0]["json"]["input"] == "Điều kiện ly hôn đơn phương"


def test_embed_texts_returns_empty_when_no_inputs() -> None:
    from services.qdrant_service import embed_texts

    with patch("services.qdrant_service.httpx.Client") as mock_client:
        result = embed_texts([])

    assert result == []
    mock_client.assert_not_called()


def test_embed_texts_raises_when_ollama_returns_no_embedding() -> None:
    from services.qdrant_service import embed_texts

    fake_client = FakeHttpClient([FakeResponse({})] * 10)

    with patch("services.qdrant_service.httpx.Client", return_value=fake_client):
        try:
            embed_texts(["abc"])
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "no embeddings" in str(exc).lower()


def test_embed_texts_retries_with_ascii_normalized_text_after_500() -> None:
    from services.qdrant_service import embed_texts
    import httpx

    request = httpx.Request("POST", "http://localhost:11434/api/embed")
    failing_response = httpx.Response(500, request=request)

    class FailingThenWorkingClient:
        def __init__(self):
            self.calls = []
            self.count = 0
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return None
        def post(self, url: str, json: dict):
            self.calls.append({"url": url, "json": json})
            self.count += 1
            if self.count == 1:
                raise httpx.HTTPStatusError("500", request=request, response=failing_response)
            return FakeResponse({"embeddings": [[0.1] * 1024]})

    fake_client = FailingThenWorkingClient()
    text = "Chương 17, loại 13, khoản 02; hạng 03; Quỹ Bảo hiểm xã hội"

    with patch("services.qdrant_service.httpx.Client", return_value=fake_client):
        vectors = embed_texts([text])

    assert len(vectors) == 1
    assert len(fake_client.calls) == 2
    assert fake_client.calls[0]["json"]["input"] == text
    assert fake_client.calls[1]["json"]["input"] != text
    assert "Chuong 17" in fake_client.calls[1]["json"]["input"]


# ─── ingest_articles: full-field payload tests ─────────────────────────────────

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


# ─── search_legal_context: 5-field return shape ──────────────────────────────

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
