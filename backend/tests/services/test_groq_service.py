from types import SimpleNamespace
from unittest.mock import patch

import services.groq_service as groq_service
from services.groq_service import (
    FALLBACK_ANSWER,
    FALLBACK_POOL_EXHAUSTED_ANSWER,
    generate_answer,
    generate_structured_answer,
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


# ---------- generate_answer (text path) ----------

def test_generate_answer_returns_model_content() -> None:
    set_key_pool("key-1")

    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response("Câu trả lời Groq")

        answer = generate_answer(
            question="Ly hôn là gì?",
            contexts=[{"title": "Luật HNGĐ", "content_text": "Ngữ cảnh pháp luật"}],
        )

    assert answer == "Câu trả lời Groq"
    assert groq_service._next_key_index == 0


def test_generate_answer_passes_system_prompt_and_history() -> None:
    set_key_pool("key-1")

    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response("ok")

        generate_answer(
            question="Tiếp theo thì sao?",
            contexts=[{"content_text": "ctx"}],
            history=[
                {"role": "user", "content": "Câu hỏi trước"},
                {"role": "assistant", "content": "Trả lời trước"},
            ],
        )

    call_kwargs = mock_groq.return_value.chat.completions.create.call_args.kwargs
    messages = call_kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "luật sư tư vấn pháp luật Việt Nam" in messages[0]["content"]
    # history comes before the current user turn
    assert messages[1] == {"role": "user", "content": "Câu hỏi trước"}
    assert messages[2] == {"role": "assistant", "content": "Trả lời trước"}
    # last message is the current user question
    assert messages[-1]["role"] == "user"
    assert "Tiếp theo thì sao?" in messages[-1]["content"]
    # context chunks appear in the user message body
    assert "ctx" in messages[-1]["content"]


def test_generate_answer_omits_history_when_empty() -> None:
    set_key_pool("key-1")
    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response("ok")
        generate_answer(question="Câu hỏi đầu tiên", contexts=[{"content_text": "ctx"}])

    messages = mock_groq.return_value.chat.completions.create.call_args.kwargs["messages"]
    # system + user only
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_generate_answer_returns_fallback_when_content_missing() -> None:
    set_key_pool("key-1")
    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response(None)
        answer = generate_answer(question="q", contexts=[{"content_text": "c"}])
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
    with patch("services.groq_service.Groq", side_effect=[first_client, second_client]):
        answer = generate_answer(question="q", contexts=[{"content_text": "c"}])
    assert answer == "Từ key 2"
    assert groq_service._next_key_index == 2


def test_generate_answer_returns_pool_exhausted_fallback_when_all_keys_fail() -> None:
    set_key_pool("key-1", "key-2", "key-3")

    def raise_retryable(**_):
        raise FakeRetryableError("quota exceeded", 429)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=raise_retryable)))
    with patch("services.groq_service.Groq", side_effect=[client, client, client]):
        answer = generate_answer(question="q", contexts=[{"content_text": "c"}])
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
            generate_answer(question="q", contexts=[{"content_text": "c"}])
            raise AssertionError("Expected FakeNonRetryableError")
        except FakeNonRetryableError:
            pass
    assert len(mock_groq.call_args_list) == 1


def test_generate_answer_returns_pool_exhausted_fallback_when_no_keys_configured() -> None:
    set_key_pool()
    answer = generate_answer(question="q", contexts=[{"content_text": "c"}])
    assert answer == FALLBACK_POOL_EXHAUSTED_ANSWER


# ---------- generate_structured_answer (JSON path) ----------

def test_generate_structured_answer_uses_json_response_format() -> None:
    set_key_pool("key-1")
    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response('{"loi_chao":"Chào bạn"}')
        result = generate_structured_answer(
            question="Ly hôn thế nào?",
            contexts=[{"content_text": "Điều 51 Luật HNGĐ"}],
        )
    assert result == {"loi_chao": "Chào bạn"}
    call_kwargs = mock_groq.return_value.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_generate_structured_answer_raises_on_invalid_json() -> None:
    set_key_pool("key-1")
    with patch("services.groq_service.Groq") as mock_groq:
        mock_groq.return_value.chat.completions.create.return_value = make_response("not json {")
        try:
            generate_structured_answer(question="q", contexts=[{"content_text": "c"}])
            raise AssertionError("Expected ValueError")
        except ValueError as exc:
            assert "JSON" in str(exc)
