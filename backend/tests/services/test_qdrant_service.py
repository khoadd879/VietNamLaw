"""Tests for qdrant_service.py - embedding and search functionality."""
from unittest.mock import MagicMock, patch


def test_embed_texts_returns_correct_dims() -> None:
    """Call embed_texts with known strings, verify 768-dim vectors returned."""
    from services.qdrant_service import embed_texts

    test_texts = ["Điều kiện ly hôn đơn phương", "Quyền nuôi con sau ly hôn"]

    # Mock the Gemini client
    mock_embedding_values = [0.1] * 768
    mock_embedding = MagicMock()
    mock_embedding.embeddings = [MagicMock(values=mock_embedding_values)]

    mock_result = MagicMock()
    mock_result.embeddings = mock_embedding.embeddings

    with patch("services.qdrant_service.genai.Client") as mock_client_class:
        mock_client_instance = MagicMock()
        mock_client_instance.models.embed_content.return_value = mock_result
        mock_client_class.return_value = mock_client_instance

        with patch("services.qdrant_service.GEMINI_API_KEY", "fake-key"):
            with patch("services.qdrant_service.GEMINI_EMBEDDING_MODEL", "embedding-001"):
                vectors = embed_texts(test_texts)

    assert len(vectors) == 2, "Should return 2 vectors for 2 inputs"
    for vector in vectors:
        assert len(vector) == 768, f"Vector should have 768 dims, got {len(vector)}"
        # Check vector values are consistent
        assert all(abs(v - 0.1) < 0.001 for v in vector), "Vector values should match mock"


def test_search_legal_context_returns_list() -> None:
    """Call search_legal_context, verify list returned."""
    from services.qdrant_service import search_legal_context

    # Mock Qdrant client search response
    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Luật quy định về ly hôn",
        "article_title": "Điều 56 - Ly hôn",
        "source_url": "https://phapdien.moj.gov.vn/article/56",
    }
    mock_point.score = 0.95

    mock_results = [mock_point]

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.search.return_value = mock_results
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 768]

            results = search_legal_context(message="Điều kiện ly hôn là gì?")

    assert isinstance(results, list), "Should return a list"
    assert len(results) == 1, "Should return 1 result"
    assert "content_text" in results[0]
    assert "article_title" in results[0]
    assert "source_url" in results[0]
    assert "score" in results[0]
    assert results[0]["score"] == 0.95


def test_search_with_filters() -> None:
    """If filters passed, verify filtering applied."""
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Quy định về hôn nhân",
        "article_title": "Chương III - Hôn nhân",
        "source_url": "https://phapdien.moj.gov.vn/chapter/3",
    }
    mock_point.score = 0.88

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.search.return_value = [mock_point]
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 768]

            # Call with filter
            filters = {"topic_title": "Luật Hôn nhân và Gia đình"}
            results = search_legal_context(
                message="Quy định về hôn nhân",
                filters=filters,
                top_k=5,
            )

    # Verify search was called
    mock_client.search.assert_called_once()
    call_kwargs = mock_client.search.call_args.kwargs

    # Verify filter was passed
    assert call_kwargs["query_filter"] is not None, "Filter should be passed"
    assert call_kwargs["limit"] == 5, "top_k should be passed as limit"
    assert call_kwargs["collection_name"] == "legal_articles"


def test_search_with_demuc_filter() -> None:
    """Verify demuc_title filter is applied correctly."""
    from services.qdrant_service import search_legal_context

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.3] * 768]

            filters = {"demuc_title": "Chương II"}
            search_legal_context(message="Nội dung", filters=filters)

    call_kwargs = mock_client.search.call_args.kwargs
    assert call_kwargs["query_filter"] is not None


def test_search_with_both_filters() -> None:
    """Verify both topic_title and demuc_title filters are applied."""
    from services.qdrant_service import search_legal_context

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.4] * 768]

            filters = {
                "topic_title": "Luật Hôn nhân",
                "demuc_title": "Điều 55",
            }
            search_legal_context(message="Ly hôn", filters=filters)

    call_kwargs = mock_client.search.call_args.kwargs
    qdrant_filter = call_kwargs["query_filter"]
    assert qdrant_filter is not None
    assert qdrant_filter.must is not None
    assert len(qdrant_filter.must) == 2, "Both filters should create 2 conditions"