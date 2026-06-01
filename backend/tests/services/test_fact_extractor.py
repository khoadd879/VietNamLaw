import json
from types import SimpleNamespace
from unittest.mock import patch

from services import fact_extractor
from services.fact_extractor import extract_facts


def make_response(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_extract_facts_parses_well_formed_json() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = json.dumps({
            "case_type": "hôn nhân gia đình",
            "extracted_facts": [
                {"key": "ngay_ket_hon", "value": "2018-03-15", "confidence": 0.95}
            ],
            "case_summary": "User kết hôn năm 2018.",
        })
        result = extract_facts("Tôi kết hôn ngày 15/3/2018")
    assert result["case_type"] == "hôn nhân gia đình"
    assert result["extracted_facts"][0]["key"] == "ngay_ket_hon"
    assert result["extracted_facts"][0]["confidence"] == 0.95


def test_extract_facts_returns_empty_on_invalid_json() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = "not json {"
        result = extract_facts("xin chào")
    assert result == {"case_type": None, "extracted_facts": [], "case_summary": None}


def test_extract_facts_returns_empty_on_empty_response() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = ""
        result = extract_facts("ok")
    assert result["extracted_facts"] == []


def test_extract_facts_passes_existing_facts_and_hint_to_llm() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = '{"case_type": null, "extracted_facts": [], "case_summary": null}'
        extract_facts(
            "thêm nữa là tôi có 1 con",
            existing_facts=[{"key": "ngay_ket_hon", "value": "2018"}],
            case_type_hint="hôn nhân gia đình",
        )
    messages = mock.call_args.args[0]
    user_text = messages[1]["content"]
    import json as _json
    payload = _json.loads(user_text)
    assert payload["existing_facts"] == [{"key": "ngay_ket_hon", "value": "2018"}]
    assert payload["case_type_hint"] == "hôn nhân gia đình"
    assert payload["new_message"] == "thêm nữa là tôi có 1 con"


def test_extract_facts_uses_json_response_format() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = '{"case_type": null, "extracted_facts": [], "case_summary": null}'
        extract_facts("m")
    assert mock.call_args.kwargs["response_format"] == {"type": "json_object"}