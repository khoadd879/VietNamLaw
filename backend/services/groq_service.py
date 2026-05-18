from threading import Lock

from groq import Groq

from core.config import GROQ_API_KEYS, GROQ_MODEL


FALLBACK_ANSWER = "Không có câu trả lời phù hợp."
FALLBACK_POOL_EXHAUSTED_ANSWER = "Hệ thống hiện không thể trả lời thêm vào lúc này. Vui lòng thử lại sau."
_RETRYABLE_KEY_ERROR_MARKERS = (
    "rate limit",
    "quota",
    "resource exhausted",
    "too many requests",
    "insufficient credits",
    "credits exceeded",
)
_next_key_index = 0
_key_rotation_lock = Lock()


def build_prompt(question: str, context_chunks: list[str]) -> str:
    context = "\n\n".join(context_chunks)
    return (
        "Bạn là trợ lý pháp luật Việt Nam. "
        "Chỉ dựa trên ngữ cảnh được cung cấp. "
        "Nếu ngữ cảnh không đủ, nói rõ là chưa đủ thông tin.\n\n"
        f"Ngữ cảnh:\n{context}\n\n"
        f"Câu hỏi: {question}"
    )


def _get_start_index() -> int:
    if not GROQ_API_KEYS:
        return 0
    with _key_rotation_lock:
        return _next_key_index % len(GROQ_API_KEYS)


def _advance_start_index(next_index: int) -> None:
    if not GROQ_API_KEYS:
        return
    with _key_rotation_lock:
        global _next_key_index
        _next_key_index = next_index % len(GROQ_API_KEYS)


def _iter_api_keys() -> list[tuple[int, str]]:
    if not GROQ_API_KEYS:
        return []

    start_index = _get_start_index()
    return [
        ((start_index + offset) % len(GROQ_API_KEYS), GROQ_API_KEYS[(start_index + offset) % len(GROQ_API_KEYS)])
        for offset in range(len(GROQ_API_KEYS))
    ]


def _is_retryable_key_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_KEY_ERROR_MARKERS)


def _generate_with_key(api_key: str, prompt: str) -> str:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    content = response.choices[0].message.content if response.choices else None
    return content or FALLBACK_ANSWER


def generate_answer(question: str, contexts: list[dict[str, str]]) -> str:
    context_chunks = [item["content_text"] for item in contexts]
    prompt = build_prompt(question=question, context_chunks=context_chunks)

    if not GROQ_API_KEYS:
        return FALLBACK_POOL_EXHAUSTED_ANSWER

    for key_index, api_key in _iter_api_keys():
        try:
            answer = _generate_with_key(api_key=api_key, prompt=prompt)
            _advance_start_index(key_index + 1)
            return answer
        except Exception as exc:
            if not _is_retryable_key_error(exc):
                raise

    _advance_start_index(_get_start_index() + 1)
    return FALLBACK_POOL_EXHAUSTED_ANSWER
