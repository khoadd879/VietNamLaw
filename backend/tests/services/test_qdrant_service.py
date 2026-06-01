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


def test_clean_html_text_strips_tags_and_keeps_vietnamese_text() -> None:
    from services.qdrant_service import clean_html_text

    html = "<html><body><h1>Điều 1</h1><p>Phạm vi điều chỉnh.</p></body></html>"

    assert clean_html_text(html) == "Điều 1\n\nPhạm vi điều chỉnh."


def test_split_document_chunks_respects_max_length() -> None:
    from services.qdrant_service import split_document_chunks

    text = "\n\n".join([
        "Đoạn 1 " * 40,
        "Đoạn 2 " * 40,
        "Đoạn 3 " * 40,
    ])

    chunks = split_document_chunks(text, max_chars=300)

    assert len(chunks) >= 2
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_search_legal_context_returns_vbpl_fields() -> None:
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Khoản 1. Nội dung được làm sạch.",
        "title": "Thông tư số 01/2026/TT-BTP",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "doc_id": "123",
        "chunk_index": 0,
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "chapter_label": None,
        "article_label": None,
        "chunk_level": "paragraph",
        "total_chunks": None,
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
            results = search_legal_context(message="Thông tư về hộ tịch")

    assert results == [{
        "content_text": "Khoản 1. Nội dung được làm sạch.",
        "title": "Thông tư số 01/2026/TT-BTP",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "doc_id": "123",
        "chunk_index": 0,
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "chapter_label": None,
        "article_label": None,
        "chunk_level": "paragraph",
        "total_chunks": None,
        "relationships": [],
        "score": 0.95,
    }]


def test_search_with_loai_van_ban_filter_passes_filter_to_qdrant() -> None:
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
                message="Quy định về công chứng",
                filters={"loai_van_ban": "Thông tư", "co_quan_ban_hanh": "Bộ Tư pháp"},
                top_k=5,
            )

    qdrant_filter = mock_client.query_points.call_args.kwargs["query_filter"]
    assert qdrant_filter is not None
    assert len(qdrant_filter.must) == 2
    assert mock_client.query_points.call_args.kwargs["limit"] == 5


def test_ingest_articles_stores_vbpl_chunk_payload() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "content_text": "Khoản 1. Quy định thử nghiệm.",
        "title": "Thông tư số 01/2026/TT-BTP",
        "so_ky_hieu": "01/2026/TT-BTP",
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "linh_vuc": "Hộ tịch",
        "nganh": "Tư pháp",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point.payload["title"] == "Thông tư số 01/2026/TT-BTP"
    assert point.payload["doc_id"] == "123"
    assert point.payload["chunk_index"] == 0
    assert point.payload["loai_van_ban"] == "Thông tư"


def test_ingest_articles_calls_embed_with_documents() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "content_text": "Quy định về ly hôn",
        "title": "Thông tư số 01/2026/TT-BTP",
        "so_ky_hieu": "01/2026/TT-BTP",
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "linh_vuc": "Hôn nhân",
        "nganh": "Tư pháp",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
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


def test_detect_doc_format_returns_law_for_repeated_dieu_markers() -> None:
    from services.qdrant_service import detect_doc_format

    text = "\n\n".join([
        "Chương I\nNhững quy định chung",
        "Điều 1. Phạm vi điều chỉnh",
        "Điều 2. Đối tượng áp dụng",
        "Điều 3. Giải thích từ ngữ",
    ])

    assert detect_doc_format(text) == "law"


def test_detect_doc_format_returns_decision_for_decision_style_text() -> None:
    from services.qdrant_service import detect_doc_format

    text = "\n\n".join([
        "ỦY BAN NHÂN DÂN TỈNH X",
        "QUYẾT ĐỊNH",
        "Về việc ban hành Quy chế phối hợp liên ngành",
        "Điều 1. Ban hành kèm theo Quyết định này Quy chế phối hợp liên ngành.",
        "Điều 2. Chánh Văn phòng Ủy ban nhân dân tỉnh chịu trách nhiệm thi hành Quyết định này.",
    ])

    assert detect_doc_format(text) == "decision"


def test_split_legal_chunks_preserves_chapter_and_article_labels() -> None:
    from services.qdrant_service import split_legal_chunks

    text = "\n\n".join([
        "Chương I",
        "Những quy định chung",
        "Điều 1. Phạm vi điều chỉnh\nKhoản 1. Văn bản này quy định phạm vi điều chỉnh.",
        "Điều 2. Đối tượng áp dụng\nKhoản 1. Văn bản này áp dụng với cơ quan, tổ chức, cá nhân.",
    ])

    chunks = split_legal_chunks(text, max_chars=120)

    # With khoan-aware splitting, we get khoan-level chunks
    assert len(chunks) == 2
    assert chunks[0]["chunk_level"] in ("khoan", "sub_khoan")
    assert chunks[0]["chapter_label"] == "Chương I"
    assert chunks[0]["article_label"] == "Điều 1"
    assert chunks[0]["khoan_label"] == "1"
    assert "Điều 1. Phạm vi điều chỉnh" in chunks[0]["content_text"]
    assert chunks[1]["chapter_label"] == "Chương I"
    assert chunks[1]["article_label"] == "Điều 2"
    assert chunks[1]["khoan_label"] == "1"
    assert all("total_chunks" not in chunk for chunk in chunks)


def test_split_legal_chunks_sub_splits_only_within_one_article() -> None:
    from services.qdrant_service import split_legal_chunks

    article_1 = "\n".join([
        "Điều 1. Phạm vi điều chỉnh",
        "Khoản 1. " + ("Nội dung của điều một. " * 20),
        "Khoản 2. " + ("Tiếp tục quy định trong cùng điều. " * 20),
        "Khoản 3. " + ("Phần cuối của điều một. " * 20),
    ])
    article_2 = "Điều 2. Hiệu lực thi hành\nKhoản 1. Văn bản này có hiệu lực kể từ ngày ban hành."
    text = f"Chương I\nNhững quy định chung\n\n{article_1}\n\n{article_2}"

    chunks = split_legal_chunks(text, max_chars=240)

    dieu_1_chunks = [chunk for chunk in chunks if chunk["article_label"] == "Điều 1"]
    dieu_2_chunks = [chunk for chunk in chunks if chunk["article_label"] == "Điều 2"]

    # With khoan-aware splitting, chunks are split by khoan boundaries
    assert len(dieu_1_chunks) >= 2
    assert all(chunk["chunk_level"] in ("khoan", "sub_khoan", "sub_article") for chunk in dieu_1_chunks)
    assert all("Điều 2. Hiệu lực thi hành" not in chunk["content_text"] for chunk in dieu_1_chunks)
    assert len(dieu_2_chunks) == 1
    assert dieu_2_chunks[0]["chunk_level"] in ("khoan", "article", "sub_article")
    assert "Điều 2. Hiệu lực thi hành" in dieu_2_chunks[0]["content_text"]
    assert all("total_chunks" not in chunk for chunk in chunks)


def test_split_legal_chunks_falls_back_to_paragraph_mode_for_decisions() -> None:
    from services.qdrant_service import split_legal_chunks

    text = "\n\n".join([
        "ỦY BAN NHÂN DÂN TỈNH X",
        "QUYẾT ĐỊNH",
        "Về việc ban hành Quy chế phối hợp liên ngành",
        "Điều 1. Ban hành kèm theo Quyết định này Quy chế phối hợp liên ngành.",
        "Điều 2. Chánh Văn phòng Ủy ban nhân dân tỉnh chịu trách nhiệm thi hành Quyết định này.",
    ])

    chunks = split_legal_chunks(text, max_chars=80)

    assert len(chunks) >= 2
    assert all(chunk["chunk_level"] == "paragraph" for chunk in chunks)
    assert all(chunk["chapter_label"] is None for chunk in chunks)
    assert all(chunk["article_label"] is None for chunk in chunks)
    first_chunk_text = chunks[0]["content_text"]
    assert "ỦY BAN NHÂN DÂN TỈNH X" in first_chunk_text
    assert "QUYẾT ĐỊNH" in first_chunk_text


def test_ingest_articles_stores_legal_structure_metadata_on_payload() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "total_chunks": 3,
        "chunk_level": "sub_article",
        "chapter_label": "Chương I",
        "article_label": "Điều 1",
        "content_text": "Điều 1. Phạm vi điều chỉnh\nKhoản 1. Quy định thử nghiệm.",
        "title": "Thông tư số 01/2026/TT-BTP",
        "so_ky_hieu": "01/2026/TT-BTP",
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "linh_vuc": "Hộ tịch",
        "nganh": "Tư pháp",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point.payload["chunk_level"] == "sub_article"
    assert point.payload["chapter_label"] == "Chương I"
    assert point.payload["article_label"] == "Điều 1"
    assert point.payload["total_chunks"] == 3


def test_ingest_articles_stores_relationships_in_payload() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "content_text": "Khoản 1. Quy định thử nghiệm.",
        "title": "Thông tư số 01/2026/TT-BTP",
        "so_ky_hieu": "01/2026/TT-BTP",
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "linh_vuc": "Hộ tịch",
        "nganh": "Tư pháp",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "relationships": [
            {"other_doc_id": "456", "relationship": "sửa đổi"},
            {"other_doc_id": "789", "relationship": "bãi bỏ"},
        ],
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point.payload["relationships"] == [
        {"other_doc_id": "456", "relationship": "sửa đổi"},
        {"other_doc_id": "789", "relationship": "bãi bỏ"},
    ]


def test_ingest_articles_stores_empty_relationships_when_missing() -> None:
    from services.qdrant_service import ingest_articles

    article = {
        "id": "123:0",
        "doc_id": "123",
        "chunk_index": 0,
        "content_text": "Khoản 1. Quy định thử nghiệm.",
        "title": "Thông tư số 01/2026/TT-BTP",
        "so_ky_hieu": "01/2026/TT-BTP",
        "loai_van_ban": "Thông tư",
        "co_quan_ban_hanh": "Bộ Tư pháp",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "linh_vuc": "Hộ tịch",
        "nganh": "Tư pháp",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
    }

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.2] * 1024]
            ingest_articles([article])

    point = mock_client.upsert.call_args.kwargs["points"][0]
    assert point.payload["relationships"] == []


def test_search_legal_context_returns_relationships() -> None:
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Điều 1. Nội dung được làm sạch.",
        "title": "Luật mẫu",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "doc_id": "123",
        "chunk_index": 0,
        "chunk_level": "article",
        "chapter_label": "Chương I",
        "article_label": "Điều 1",
        "total_chunks": 5,
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "relationships": [
            {"other_doc_id": "456", "relationship": "sửa đổi"},
        ],
    }
    mock_point.score = 0.91

    mock_response = MagicMock()
    mock_response.points = [mock_point]

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            results = search_legal_context(message="Điều 1 luật mẫu")

    assert results[0]["relationships"] == [{"other_doc_id": "456", "relationship": "sửa đổi"}]


def test_search_legal_context_returns_empty_relationships_when_missing() -> None:
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Điều 1. Nội dung được làm sạch.",
        "title": "Luật mẫu",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "doc_id": "123",
        "chunk_index": 0,
        "chunk_level": "article",
        "chapter_label": "Chương I",
        "article_label": "Điều 1",
        "total_chunks": 5,
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
    }
    mock_point.score = 0.91

    mock_response = MagicMock()
    mock_response.points = [mock_point]

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            results = search_legal_context(message="Điều 1 luật mẫu")

    assert results[0]["relationships"] == []


def test_search_legal_context_returns_legal_chunk_metadata_fields() -> None:
    from services.qdrant_service import search_legal_context

    mock_point = MagicMock()
    mock_point.payload = {
        "content_text": "Điều 1. Nội dung được làm sạch.",
        "title": "Luật mẫu",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "doc_id": "123",
        "chunk_index": 0,
        "chunk_level": "article",
        "chapter_label": "Chương I",
        "article_label": "Điều 1",
        "total_chunks": 5,
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
    }
    mock_point.score = 0.91

    mock_response = MagicMock()
    mock_response.points = [mock_point]

    with patch("services.qdrant_service.get_qdrant_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        with patch("services.qdrant_service.embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1024]
            results = search_legal_context(message="Điều 1 luật mẫu")

    assert results == [{
        "content_text": "Điều 1. Nội dung được làm sạch.",
        "title": "Luật mẫu",
        "source_url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=123",
        "doc_id": "123",
        "chunk_index": 0,
        "chunk_level": "article",
        "chapter_label": "Chương I",
        "article_label": "Điều 1",
        "total_chunks": 5,
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "relationships": [],
        "score": 0.91,
    }]


def test_html_parser_extracts_headings():
    from services.qdrant_service import HTMLLegalParser
    html = """
    <html><body>
        <h1>CHƯƠNG I: NHỮNG QUY ĐỊNH CHUNG</h1>
        <p>Some content here</p>
        <h2>Điều 1. Phạm vi điều chỉnh</h2>
        <p>Nội dung điều 1 khoản 1.</p>
        <p>Nội dung điều 1 khoản 2.</p>
    </body></html>
    """
    parser = HTMLLegalParser()
    result = parser.parse(html)
    assert len(result['headings']) == 2
    assert result['headings'][0]['text'] == "CHƯƠNG I: NHỮNG QUY ĐỊNH CHUNG"
    assert result['headings'][0]['level'] == 1
    assert result['headings'][1]['text'] == "Điều 1. Phạm vi điều chỉnh"
    assert result['headings'][1]['level'] == 2


def test_html_parser_extracts_paragraphs():
    from services.qdrant_service import HTMLLegalParser
    html = "<p>Para 1</p><p>Para 2</p><div>Div content</div>"
    parser = HTMLLegalParser()
    result = parser.parse(html)
    assert len(result['paragraphs']) >= 2


def test_html_parser_preserves_semantic_structure():
    from services.qdrant_service import HTMLLegalParser
    html = """
    <h1>Chương I</h1>
    <h2>Điều 1.</h2>
    <p>Khoản 1. Nội dung khoản 1.</p>
    <p>Khoản 2. Nội dung khoản 2.</p>
    """
    parser = HTMLLegalParser()
    result = parser.parse(html)
    assert len(result['chapters']) == 1
    assert len(result['articles']) == 1
    assert len(result['khoans']) == 2


def test_split_legal_chunks_respects_khoan():
    from services.qdrant_service import split_legal_chunks

    text = """Chương I
Điều 1. Nội dung chính
Khoản 1. Phần mở đầu của điều này phải được hiểu theo nghĩa rộng bao gồm nhiều trường hợp khác nhau.
Khoản 2. Phần tiếp theo nói về quyền và nghĩa vụ của các bên liên quan trong quan hệ pháp luật.
Điều 2. Nội dung bổ sung"""

    chunks = split_legal_chunks(text, max_chars=300)
    assert len(chunks) >= 2
    for chunk in chunks:
        if chunk.get("chunk_level") in ("khoan", "sub_khoan"):
            assert "Khoản" in str(chunk) or chunk.get("khoan_label")


def test_split_legal_chunks_long_article():
    from services.qdrant_service import split_legal_chunks

    text = "Điều 1. Title\n" + ("x" * 200 + "\n\n") * 20

    chunks = split_legal_chunks(text, max_chars=500)
    for chunk in chunks:
        if chunk.get("chunk_level") in ("sub_article", "sub_khoan"):
            assert len(chunk["content_text"]) <= 500


def test_split_legal_chunks_preserves_metadata():
    from services.qdrant_service import split_legal_chunks

    text = """CHƯƠNG II: TỔ CHỨC VÀ HOẠT ĐỘNG
Điều 10. Thẩm quyền
Nội dung điều 10 rất dài. """ + ("x" * 500)

    chunks = split_legal_chunks(text, max_chars=300)
    has_chapter_label = any(c.get("chapter_label") for c in chunks)
    assert has_chapter_label, "Should preserve chapter labels"


def test_split_legal_chunks_handles_decision_format():
    from services.qdrant_service import split_legal_chunks

    # Decision format without articles
    text = "Quyết định số 123/2020\n\n" + ("Paragraph " + "x" * 100 + "\n\n") * 10

    chunks = split_legal_chunks(text, max_chars=400)
    assert len(chunks) > 0
