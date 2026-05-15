from api.services.gemini_service import build_prompt


def test_build_prompt_includes_question_and_context() -> None:
    prompt = build_prompt(
        question="Điều kiện đơn phương ly hôn là gì?",
        context_chunks=[
            "Luật Hôn nhân và Gia đình quy định về quyền yêu cầu ly hôn.",
            "Tòa án xem xét tình trạng hôn nhân trầm trọng.",
        ],
    )

    assert "Điều kiện đơn phương ly hôn là gì?" in prompt
    assert "Luật Hôn nhân và Gia đình" in prompt
    assert "Tòa án xem xét" in prompt