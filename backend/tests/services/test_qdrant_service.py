from unittest.mock import MagicMock, patch


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

    fake_client = FakeHttpClient([FakeResponse({})])

    with patch("services.qdrant_service.httpx.Client", return_value=fake_client):
        try:
            embed_texts(["abc"])
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "no embedding" in str(exc).lower()


def test_search_legal_context_returns_formatted_results() -> None:
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Luật quy định về ly hôn",
        "article_title": "Điều 56 - Ly hôn",
        "source_url": "https://phapdien.moj.gov.vn/article/56",
    }
    mock_point.score = 0.95

    mock_response = MagicMock()
    mock_response.points = [mock_point]

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            results = search_legal_context(message="Điều kiện ly hôn là gì?")

    assert len(results) == 1
    assert results[0]["content_text"] == "Luật quy định về ly hôn"
    assert results[0]["article_title"] == "Điều 56 - Ly hôn"
    assert results[0]["source_url"] == "https://phapdien.moj.gov.vn/article/56"
    assert results[0]["score"] == 0.95


def test_search_with_topic_filter_passes_filter_to_qdrant() -> None:
    from services.qdrant_service import search_legal_context

    mock_response = MagicMock()
    mock_response.points = []

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            search_legal_context(
                message="Quy định về hôn nhân",
                filters={"topic_title": "Luật Hôn nhân và Gia đình"},
                top_k=5,
            )

    call_kwargs = mock_client.query_points.call_args.kwargs
    assert call_kwargs["query_filter"] is not None
    assert call_kwargs["limit"] == 5
    assert call_kwargs["collection_name"] == "legal_articles"


def test_search_with_both_filters_creates_two_conditions() -> None:
    from services.qdrant_service import search_legal_context

    mock_response = MagicMock()
    mock_response.points = []

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.4] * 1024]
            search_legal_context(
                message="Ly hôn",
                filters={
                    "topic_title": "Luật Hôn nhân",
                    "demuc_title": "Điều 55",
                },
            )

    qdrant_filter = mock_client.query_points.call_args.kwargs["query_filter"]
    assert qdrant_filter is not None
    assert qdrant_filter.must is not None
    assert len(qdrant_filter.must) == 2


def test_ingest_articles_calls_embed_with_documents() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "art-1",
        "content_text": "Quy định về ly hôn",
        "article_title": "Điều 56",
        "article_anchor": "art-1",
        "topic_title": "Luật Hôn nhân",
        "topic_id": "t-1",
        "demuc_title": "Mục 1",
        "demuc_id": "d-1",
        "source_url": "https://example.com/56",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    args, kwargs = mock_embed.call_args
    texts = args[0] if args else kwargs.get("texts")
    assert texts == ["Quy định về ly hôn"]
