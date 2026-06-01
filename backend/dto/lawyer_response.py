from pydantic import BaseModel, Field, field_validator


class LawyerResponse(BaseModel):
    """Structured response from the lawyer LLM (Sprint 1 schema)."""

    loi_chao: str = Field(default="", max_length=500)
    tom_tat_vu_viec: str = Field(default="", max_length=1500)
    phan_tich_phap_ly: str = Field(default="", max_length=4000)
    phuong_an_khuyen_nghi: list[str] = Field(default_factory=list)
    rui_ro_can_luu_y: list[str] = Field(default_factory=list)
    cau_hoi_hoi_them: list[str] = Field(default_factory=list)
    disclaimer: str = Field(default="", max_length=1000)
    trich_dan_nguon: list[str] = Field(default_factory=list)

    @field_validator("phuong_an_khuyen_nghi", "rui_ro_can_luu_y", "cau_hoi_hoi_them", "trich_dan_nguon")
    @classmethod
    def _limit_list_size(cls, v: list[str]) -> list[str]:
        # Defensive cap: LLMs sometimes return 50+ items.
        return v[:20]

    @field_validator("disclaimer")
    @classmethod
    def _ensure_disclaimer_nonempty(cls, v: str) -> str:
        if not v.strip():
            return (
                "Đây là tư vấn pháp luật mang tính tham khảo, không thay thế ý kiến "
                "luật sư hành nghề cụ thể cho hồ sơ của bạn. Trường hợp phức tạp, bạn "
                "nên liên hệ luật sư/Văn phòng luật sư/Luật sư đoàn tại địa phương."
            )
        return v
