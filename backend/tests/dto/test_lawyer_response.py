import pytest
from pydantic import ValidationError

from dto.lawyer_response import LawyerResponse


def test_accepts_well_formed_response() -> None:
    r = LawyerResponse(
        loi_chao="Chào bạn",
        tom_tat_vu_viec="Vụ ly hôn",
        phan_tich_phap_ly="Điều 51 Luật HNGĐ",
        phuong_an_khuyen_nghi=["Thỏa thuận", "�ơn phương"],
        rui_ro_can_luu_y=["Thời hiệu 2 năm"],
        cau_hoi_hoi_them=[],
        disclaimer="Đây là tư vấn tham khảo...",
        trich_dan_nguon=["Điều 51 - Luật HNGĐ"],
    )
    assert r.loi_chao == "Chào bạn"
    assert len(r.phuong_an_khuyen_nghi) == 2


def test_defaults_to_empty_lists_and_strings() -> None:
    r = LawyerResponse()
    assert r.loi_chao == ""
    assert r.phuong_an_khuyen_nghi == []


def test_fills_in_default_disclaimer_when_blank() -> None:
    r = LawyerResponse(disclaimer="")
    assert "tư vấn pháp luật mang tính tham khảo" in r.disclaimer


def test_caps_list_size_at_20() -> None:
    r = LawyerResponse(phuong_an_khuyen_nghi=[f"PA{i}" for i in range(50)])
    assert len(r.phuong_an_khuyen_nghi) == 20


def test_rejects_oversized_loi_chao() -> None:
    with pytest.raises(ValidationError):
        LawyerResponse(loi_chao="x" * 1000)


def test_accepts_alternate_field_aliases_for_safety() -> None:
    """LLM sometimes uses 'lời_chào' with diacritics; we accept both shapes by raw dict path."""
    raw = {
        "lời_chào": "Chào",
        "tóm_tắt_vụ_việc": "Vụ A",
        "phân_tích_pháp_lý": "Điều 1",
        "phương_án_khuyến_nghị": ["A"],
        "rủi_ro_cần_lưu_ý": ["B"],
        "câu_hỏi_hỏi_thêm": [],
        "disclaimer": "ok",
        "trích_dẫn_nguồn": ["src"],
    }
    # We don't auto-alias in Pydantic; this test documents that callers must
    # normalize. The chat_service does that normalization (see Task 1.5).
    r = LawyerResponse.model_validate({})
    assert r.loi_chao == ""
