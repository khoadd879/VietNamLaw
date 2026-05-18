from services.answer_service import generate_answer


def test_answer_service_exports_generate_answer() -> None:
    assert callable(generate_answer)
