from types import SimpleNamespace
from unittest.mock import patch

import services.groq_service as groq_service
from services.groq_service import (
    FALLBACK_ANSWER,
    FALLBACK_POOL_EXHAUSTED_ANSWER,
    build_prompt,
    generate_answer,
)


class FakeRetryableError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class FakeNonRetryableError(Exception):
    pass


def make_response(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def set_key_pool(*keys: str) -> None:
    groq_service.GROQ_API_KEYS[:] = list(keys)
    groq_service._next_key_index = 0


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


def test_generate_answer_returns_model_content() -> None:
    set_key_pool("key-1")

    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response("Câu trả lời Groq")

        answer = generate_answer(
            question="Ly hôn là gì?",
            contexts=[{"content_text": "Ngữ cảnh pháp luật"}],
        )

    assert answer == "Câu trả lời Groq"
    assert groq_service._next_key_index == 0


def test_generate_answer_returns_fallback_when_content_missing() -> None:
    set_key_pool("key-1")

    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response(None)

        answer = generate_answer(
            question="Ly hôn là gì?",
            contexts=[{"content_text": "Ngữ cảnh pháp luật"}],
        )

    assert answer == FALLBACK_ANSWER


def test_generate_answer_rotates_to_next_key_on_retryable_error() -> None:
    set_key_pool("key-1", "key-2", "key-3")

    first_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: (_ for _ in ()).throw(FakeRetryableError("rate limit", 429))
            )
        )
    )
    second_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_: make_response("Từ key 2"))
        )
    )

    with patch("services.groq_service.Groq", side_effect=[first_client, second_client]) as mock_groq:
        answer = generate_answer(
            question="Ly hôn là gì?",
            contexts=[{"content_text": "Ngữ cảnh pháp luật"}],
        )

    assert answer == "Từ key 2"
    assert mock_groq.call_args_list[0].kwargs["api_key"] == "key-1"
    assert mock_groq.call_args_list[1].kwargs["api_key"] == "key-2"
    assert groq_service._next_key_index == 2


def test_generate_answer_returns_pool_exhausted_fallback_when_all_keys_fail() -> None:
    set_key_pool("key-1", "key-2", "key-3")

    def raise_retryable(**_):
        raise FakeRetryableError("quota exceeded", 429)

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=raise_retryable)
        )
    )

    with patch("services.groq_service.Groq", side_effect=[client, client, client]):
        answer = generate_answer(
            question="Ly hôn là gì?",
            contexts=[{"content_text": "Ngữ cảnh pháp luật"}],
        )

    assert answer == FALLBACK_POOL_EXHAUSTED_ANSWER


def test_generate_answer_raises_non_retryable_error_without_burning_pool() -> None:
    set_key_pool("key-1", "key-2", "key-3")

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: (_ for _ in ()).throw(FakeNonRetryableError("bad request"))
            )
        )
    )

    with patch("services.groq_service.Groq", return_value=client) as mock_groq:
        try:
            generate_answer(
                question="Ly hôn là gì?",
                contexts=[{"content_text": "Ngữ cảnh pháp luật"}],
            )
            raise AssertionError("Expected FakeNonRetryableError")
        except FakeNonRetryableError:
            pass

    assert len(mock_groq.call_args_list) == 1


def test_generate_answer_returns_pool_exhausted_fallback_when_no_keys_configured() -> None:
    set_key_pool()

    answer = generate_answer(
        question="Ly hôn là gì?",
        contexts=[{"content_text": "Ngữ cảnh pháp luật"}],
    )

    assert answer == FALLBACK_POOL_EXHAUSTED_ANSWER


def test_generate_answer_advances_round_robin_after_success() -> None:
    set_key_pool("key-1", "key-2", "key-3")

    clients = [
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: make_response("A")))),
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: make_response("B")))),
    ]

    with patch("services.groq_service.Groq", side_effect=clients) as mock_groq:
        first_answer = generate_answer(
            question="Câu hỏi 1",
            contexts=[{"content_text": "Ngữ cảnh 1"}],
        )
        second_answer = generate_answer(
            question="Câu hỏi 2",
            contexts=[{"content_text": "Ngữ cảnh 2"}],
        )

    assert first_answer == "A"
    assert second_answer == "B"
    assert mock_groq.call_args_list[0].kwargs["api_key"] == "key-1"
    assert mock_groq.call_args_list[1].kwargs["api_key"] == "key-2"
