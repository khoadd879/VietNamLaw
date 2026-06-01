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