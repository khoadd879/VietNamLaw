import json
import logging
from threading import Lock

from groq import Groq

from core.config import GROQ_API_KEYS, GROQ_MODEL
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

LAWYER_PERSONA_PROMPT = "lawyer_persona_v1"

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


def _format_context_chunk(item: dict) -> str:
    title = item.get("title") or "Văn bản pháp luật"
    text = item.get("content_text", "")
    return f"[{title}]\n{text}"


def _build_user_message(question: str, contexts: list[dict]) -> str:
    parts = ["NGỮ CẢNH PHÁP LÝ:"]
    chunks = [_format_context_chunk(c) for c in contexts]
    if chunks:
        parts.extend(chunks)
    else:
        parts.append("(rỗng — không tìm thấy điều luật phù hợp, hãy hỏi user thêm facts)")
    parts.append("")
    parts.append("CÂU HỎI / YÊU CẦU TƯ VẤN HIỆN TẠI:")
    parts.append(question)
    return "\n".join(parts)


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
        (
            (start_index + offset) % len(GROQ_API_KEYS),
            GROQ_API_KEYS[(start_index + offset) % len(GROQ_API_KEYS)],
        )
        for offset in range(len(GROQ_API_KEYS))
    ]


def _is_retryable_key_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_KEY_ERROR_MARKERS)


def _generate_with_key(
    api_key: str,
    messages: list[dict],
    response_format: dict | None = None,
) -> str:
    client = Groq(api_key=api_key)
    create_kwargs = dict(model=GROQ_MODEL, messages=messages)
    if response_format is not None:
        create_kwargs["response_format"] = response_format
    response = client.chat.completions.create(**create_kwargs)
    content = response.choices[0].message.content if response.choices else None
    return content or FALLBACK_ANSWER


def _run_pooled(
    messages: list[dict],
    response_format: dict | None,
    empty_fallback: str,
) -> str:
    if not GROQ_API_KEYS:
        return empty_fallback

    for key_index, api_key in _iter_api_keys():
        try:
            content = _generate_with_key(api_key, messages, response_format)
            _advance_start_index(key_index + 1)
            return content or empty_fallback
        except Exception as exc:
            if not _is_retryable_key_error(exc):
                logger.exception("Non-retryable Groq error")
                raise
            logger.warning("Retryable Groq error on key %d: %s", key_index, exc)

    _advance_start_index(_get_start_index() + 1)
    return empty_fallback


def generate_answer(
    question: str,
    contexts: list[dict[str, str]],
    history: list[dict[str, str]] | None = None,
) -> str:
    """Text answer path. Kept for fallback and non-structured uses."""
    system_prompt = load_prompt(LAWYER_PERSONA_PROMPT)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": _build_user_message(question, contexts)})
    return _run_pooled(messages, response_format=None, empty_fallback=FALLBACK_POOL_EXHAUSTED_ANSWER)


def generate_structured_answer(
    question: str,
    contexts: list[dict[str, str]],
    history: list[dict[str, str]] | None = None,
) -> dict:
    """JSON answer path. Returns parsed dict. Raises ValueError on invalid JSON."""
    system_prompt = load_prompt(LAWYER_PERSONA_PROMPT)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": _build_user_message(question, contexts)})

    raw = _run_pooled(
        messages,
        response_format={"type": "json_object"},
        empty_fallback="",
    )
    if not raw:
        raise ValueError("Empty response from LLM")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %r", raw[:500])
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
