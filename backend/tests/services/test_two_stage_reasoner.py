import json
from types import SimpleNamespace
from unittest.mock import patch

from services import two_stage_reasoner
from services.two_stage_reasoner import two_stage_reason


def test_stage1_extracts_then_stage2_synthesizes() -> None:
    extracted = {
        "case_type": "hôn nhân gia đình",
        "extracted_facts": [{"key": "ngay_ket_hon", "value": "2018", "confidence": 0.9}],
        "case_summary": "User kết hôn 2018.",
    }
    synth_payload = {
        "loi_chao": "Chào",
        "tom_tat_vu_viec": "Ly hôn",
        "phan_tich_phap_ly": "Điều 51",
        "phuong_an_khuyen_nghi": ["A"],
        "rui_ro_can_luu_y": ["B"],
        "cau_hoi_hoi_them": [],
        "disclaimer": "ok",
        "trich_dan_nguon": ["Điều 51"],
    }

    with patch("services.two_stage_reasoner.extract_facts", return_value=extracted) as mock_extract, \
         patch("services.two_stage_reasoner._run_pooled", return_value=json.dumps(synth_payload)) as mock_run:
        result = two_stage_reason(
            message="Tôi kết hôn 2018",
            contexts=[{"title": "Luật HNGĐ", "content_text": "Điều 51"}],
            history=None,
            existing_facts=[],
            case_type=None,
            case_summary=None,
        )
    assert mock_extract.called
    assert mock_run.called
    assert result["structured"]["loi_chao"] == "Chào"
    assert result["updated_case_type"] == "hôn nhân gia đình"
    assert result["updated_case_summary"] == "User kết hôn 2018."


def test_synthesizer_receives_case_brief_in_user_message() -> None:
    extracted = {
        "case_type": "lao động",
        "extracted_facts": [{"key": "muc_luong", "value": "20tr", "confidence": 0.9}],
        "case_summary": "Lương 20tr.",
    }
    captured = {}
    def fake_run(messages, **kwargs):
        captured["user_text"] = messages[-1]["content"]
        return json.dumps({
            "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
            "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
            "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
        })
    with patch("services.two_stage_reasoner.extract_facts", return_value=extracted), \
         patch("services.two_stage_reasoner._run_pooled", side_effect=fake_run):
        two_stage_reason(
            message="Lương tôi 20tr",
            contexts=[],
            history=[],
            existing_facts=[],
            case_type=None,
            case_summary=None,
        )
    assert "case_type: lao động" in captured["user_text"]
    assert "muc_luong: 20tr" in captured["user_text"]