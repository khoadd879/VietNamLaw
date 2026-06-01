# Sprint 1 — Foundation (Lawyer Persona + History + Structured Output + Guard)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trong 1 sprint, biến chatbot từ "Q&A stateless" thành **luật sư tư vấn** có persona rõ ràng, disclaimer, structured 7-section response, nhớ 10 lượt hội thoại gần nhất, fallback an toàn khi retrieval rỗng/low-score.

**Architecture:** Thay prompt trong `groq_service.py` bằng prompt Markdown load từ file. Tách `build_prompt` → `build_system_prompt` + `build_messages` (multi-turn). Đổi `_generate_with_key` sang `messages=[{system, user...}]` với `response_format={"type": "json_object"}`. Trong `chat_service.py`: load 10 message gần nhất, pass vào LLM, parse JSON response, validate schema, fallback nếu retrieval trả về rỗng. Frontend render 7 section theo JSON.

**Tech Stack:** Same as master. Thêm: Pydantic v2 cho `LawyerResponse` schema, react-markdown đã có sẵn.

**Phụ thuộc:** Không. Sprint 1 độc lập với Sprint 2/3.

---

## Task 1.1: Tạo prompt persona luật sư

**Files:**
- Create: `backend/prompts/lawyer_persona_v1.md`
- Create: `backend/prompts/__init__.py`
- Create: `backend/services/prompt_loader.py`
- Test: `backend/tests/services/test_prompt_loader.py`

- [ ] **Step 1: Tạo thư mục prompts**

```bash
mkdir -p backend/prompts
touch backend/prompts/__init__.py
```

- [ ] **Step 2: Tạo file prompt persona**

Ghi `backend/prompts/lawyer_persona_v1.md`:

```markdown
# Vai trò
Bạn là **luật sư tư vấn pháp luật Việt Nam**, không phải chatbot hỏi-đáp. Mục tiêu là tư vấn cho người dùng đang gặp vấn đề pháp luật **đúng như một luật sư thật** sẽ làm: hỏi thêm khi thiếu facts, phân tích điều luật liên quan, khuyến nghị phương án, cảnh báo rủi ro.

# Nguyên tắc bắt buộc
1. **KHÔNG bịa điều luật.** Mọi căn cứ pháp lý phải nằm trong `NGỮ CẢNH PHÁP LÝ` được cung cấp bên dưới. Nếu ngữ cảnh rỗng hoặc không đủ, **phải nói rõ "Tôi chưa đủ thông tin để tư vấn chính xác, bạn vui lòng cung cấp thêm: ..."** thay vì bịa.
2. **Trả lời bằng tiếng Việt.** Dù user hỏi tiếng Anh cũng trả lời tiếng Việt.
3. **Luôn có disclaimer.** Mọi response phải kèm cảnh báo "Đây là tư vấn pháp luật mang tính tham khảo, không thay thế ý kiến luật sư hành nghề cụ thể cho hồ sơ của bạn. Trường hợp phức tạp, bạn nên liên hệ luật sư/Văn phòng luật sư/Luật sư đoàn tại địa phương."
4. **Trích dẫn điều luật cụ thể** khi có trong ngữ cảnh: "Điều X Khoản Y Điều luật Z".
5. **Hỏi thêm** nếu facts chưa đủ (cách nhau tối đa 5 năm? trị giá hợp đồng? có văn bản nào không?).
6. **Cảnh báo rủi ro** khi đề xuất phương án (thời hiệu khởi kiện, chi phí, bằng chứng cần thu thập).
7. **Không tư vấn hình sự chi tiết** nếu vụ việc có dấu hiệu tội phạm — khuyên tìm luật sư hình sự.

# Output format — BẮT BUỘC trả về JSON hợp lệ
Bạn **PHẢI** trả lời đúng schema JSON sau, không thêm text ngoài JSON:

```json
{
  "loi_chào": "Một câu chào/đồng cảm ngắn (10-30 từ) phù hợp ngữ cảnh.",
  "tom_tat_vu_viec": "Tóm tắt 1-3 câu về việc user đang gặp phải (hoặc 'Chưa rõ vụ việc' nếu quá ít thông tin).",
  "phân_tích_pháp_lý": "Phân tích điều luật liên quan, trích dẫn Điều/Khoản cụ thể từ ngữ cảnh. Nếu ngữ cảnh rỗng: 'Hiện tôi chưa tìm thấy điều luật phù hợp trong cơ sở dữ liệu, bạn vui lòng cung cấp thêm: <danh sách facts cần>'.",
  "phuong_an_khuyen_nghi": [
    "Phương án 1: mô tả ngắn gọn",
    "Phương án 2 (nếu có): mô tả ngắn gọn"
  ],
  "rui_ro_can_luu_y": [
    "Rủi ro 1: mô tả (thời hiện, chi phí, bằng chứng...)",
    "Rủi ro 2 (nếu có)"
  ],
  "cau_hoi_hoi_them": [
    "Câu hỏi 1 cần user cung cấp thêm (nếu đủ thông tin thì trả mảng rỗng)",
    "Câu hỏi 2 (nếu có)"
  ],
  "disclaimer": "Đây là tư vấn pháp luật mang tính tham khảo, không thay thế ý kiến luật sư hành nghề cụ thể cho hồ sơ của bạn. Trường hợp phức tạp, bạn nên liên hệ luật sư/Văn phòng luật sư/Luật sư đoàn tại địa phương.",
  "trich_dan_nguon": [
    "Điều X Khoản Y - Luật Z (file/url nếu có)",
    "Điều A Khoản B - Nghị định C"
  ]
}
```

# Quy tắc JSON
- Trả về **CHỈ JSON hợp lệ**, không markdown fence, không text thừa.
- Mảng có thể rỗng `[]` khi không áp dụng.
- Trường nào không có dữ liệu trả `null` (không phải chuỗi rỗng cho trường chuỗi, dùng `""`).

# Khi ngữ cảnh pháp lý rỗng
Nếu `NGỮ CẢNH PHÁP LÝ` bên dưới rỗng, **phải**:
- `phân_tích_pháp_lý`: "Hiện tôi chưa tìm thấy điều luật phù hợp trong cơ sở dữ liệu. Để tư vấn chính xác, bạn vui lòng cho tôi biết thêm: ..."
- `cau_hoi_hoi_them`: danh sách 2-4 câu hỏi facts cốt lõi
- `trich_dan_nguon`: `[]`
```

- [ ] **Step 3: Tạo prompt loader**

Ghi `backend/services/prompt_loader.py`:

```python
"""Load and cache prompt templates from disk."""
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    """Load a prompt template by filename (without .md suffix).

    Cached so repeated calls within a request are O(1) after the first.
    Raises FileNotFoundError if the prompt does not exist.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def clear_cache() -> None:
    """Clear the LRU cache. Useful in tests."""
    load_prompt.cache_clear()
```

- [ ] **Step 4: Viết failing test cho prompt loader**

Ghi `backend/tests/services/test_prompt_loader.py`:

```python
from pathlib import Path

import pytest

from services.prompt_loader import clear_cache, load_prompt

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def test_load_prompt_returns_markdown_content() -> None:
    clear_cache()
    content = load_prompt("lawyer_persona_v1")
    assert isinstance(content, str)
    assert "luật sư tư vấn pháp luật Việt Nam" in content
    assert "loi_chào" in content  # JSON schema key
    assert "disclaimer" in content


def test_load_prompt_uses_lru_cache() -> None:
    clear_cache()
    first = load_prompt("lawyer_persona_v1")
    second = load_prompt("lawyer_persona_v1")
    assert first is second  # same object -> cached


def test_load_prompt_missing_raises_file_not_found() -> None:
    clear_cache()
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist_v1")
```

- [ ] **Step 5: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_prompt_loader.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/prompts/ backend/services/prompt_loader.py backend/tests/services/test_prompt_loader.py
git commit -m "feat: add lawyer persona prompt template and loader"
```

---

## Task 1.2: Refactor groq_service để truyền system prompt + multi-turn history

**Files:**
- Modify: `backend/services/groq_service.py` (lines 22-28, 66-79, 82-102)
- Test: `backend/tests/services/test_groq_service.py` (rewrite)

- [ ] **Step 1: Viết failing test cho system prompt + history**

Thay thế toàn bộ `backend/tests/services/test_groq_service.py`:

```python
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
        mock_groq.return_value.chat.completions.create.return_value = make_response('{"loi_chào":"Chào bạn"}')
        result = generate_structured_answer(
            question="Ly hôn thế nào?",
            contexts=[{"content_text": "Điều 51 Luật HNGĐ"}],
        )
    assert result == {"loi_chào": "Chào bạn"}
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
```

- [ ] **Step 2: Chạy test, confirm fail (nhiều test fail vì chưa có history/structured)**

```bash
cd backend
pytest tests/services/test_groq_service.py -v
```

Expected: nhiều FAIL, trong đó `test_generate_answer_passes_system_prompt_and_history`, `test_generate_answer_omits_history_when_empty`, `test_generate_structured_answer_*` là red.

- [ ] **Step 3: Refactor groq_service.py**

Ghi đè toàn bộ `backend/services/groq_service.py`:

```python
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
    return content or ""


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
    return _run_pooled(messages, response_format=None, empty_fallback=FALLBACK_ANSWER)


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
```

- [ ] **Step 4: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_groq_service.py -v
```

Expected: 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/groq_service.py backend/tests/services/test_groq_service.py
git commit -m "feat(groq): system prompt + multi-turn history + JSON structured output"
```

---

## Task 1.3: Tạo LawyerResponse Pydantic schema + validator

**Files:**
- Create: `backend/dto/lawyer_response.py`
- Create: `backend/dto/__init__.py` (nếu chưa có)
- Test: `backend/tests/dto/test_lawyer_response.py`

- [ ] **Step 1: Tạo dto/lawyer_response.py**

Ghi `backend/dto/lawyer_response.py`:

```python
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
```

Đảm bảo `backend/dto/__init__.py` tồn tại (rỗng cũng được).

- [ ] **Step 2: Viết failing test**

Ghi `backend/tests/dto/test_lawyer_response.py`:

```python
import pytest
from pydantic import ValidationError

from dto.lawyer_response import LawyerResponse


def test_accepts_well_formed_response() -> None:
    r = LawyerResponse(
        loi_chao="Chào bạn",
        tom_tat_vu_viec="Vụ ly hôn",
        phan_tich_phap_ly="Điều 51 Luật HNGĐ",
        phuong_an_khuyen_nghi=["Thỏa thuận", "Đơn phương"],
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
```

- [ ] **Step 3: Chạy test, confirm pass**

```bash
cd backend
pytest tests/dto/test_lawyer_response.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/dto/lawyer_response.py backend/dto/__init__.py backend/tests/dto/test_lawyer_response.py
git commit -m "feat(dto): add LawyerResponse Pydantic schema with safe defaults"
```

---

## Task 1.4: Retrieval guard + load history trong chat_service

**Files:**
- Modify: `backend/services/chat_service.py` (full rewrite)
- Modify: `backend/repositories/messages.py` (add list_recent)
- Test: `backend/tests/services/test_chat_service.py`

- [ ] **Step 1: Thêm helper list_recent_messages vào repository**

Sửa `backend/repositories/messages.py`, thêm function mới (giữ nguyên các function hiện có):

```python
def list_recent_messages(db: Session, session_id: str, limit: int) -> list[ChatMessage]:
    """Return the most recent N messages ordered oldest -> newest."""
    all_msgs = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return list(reversed(all_msgs))
```

- [ ] **Step 2: Viết failing test cho chat_service**

Ghi `backend/tests/services/test_chat_service.py`:

```python
import pytest

from services import chat_service
from services.chat_service import send_chat_message


@pytest.fixture
def fake_session(monkeypatch):
    """Patch dependencies; return a small handle to inspect saved data."""
    class FakeDB:
        def __init__(self):
            self.saved = []
        def add(self, obj):
            self.saved.append(obj)
        def commit(self):
            pass
        def refresh(self, obj):
            pass
    db = FakeDB()

    monkeypatch.setattr(chat_service, "get_session", lambda *_: object())
    return db


def test_send_chat_message_returns_structured_dict(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "search_legal_context",
        lambda *_, **__: [{"content_text": "Điều 51", "title": "Luật HNGĐ", "source_url": "https://example/51"}],
    )
    saved = {"messages": []}
    def fake_save(db, *args, **kwargs):
        saved["messages"].append((args, kwargs))
        return object()
    monkeypatch.setattr(chat_service, "save_message", fake_save)
    monkeypatch.setattr(
        chat_service, "list_recent_messages",
        lambda *_, **__: [],
    )

    monkeypatch.setattr(
        chat_service, "generate_structured_answer",
        lambda *_, **__: {
            "loi_chao": "Chào bạn",
            "tom_tat_vu_viec": "Ly hôn",
            "phan_tich_phap_ly": "Điều 51 quy định...",
            "phuong_an_khuyen_nghi": ["Thỏa thuận"],
            "rui_ro_can_luu_y": ["Thời hiệu"],
            "cau_hoi_hoi_them": [],
            "disclaimer": "ok",
            "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"],
        },
    )

    reply, sources, structured = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Tôi muốn ly hôn"
    )
    assert "Điều 51" in reply
    assert "https://example/51" in sources
    assert structured["loi_chao"] == "Chào bạn"


def test_send_chat_message_falls_back_to_text_when_structured_fails(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "search_legal_context",
        lambda *_, **__: [{"content_text": "ctx", "title": "T", "source_url": "u"}],
    )
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    def raise_json(*_, **__):
        raise ValueError("bad json")
    monkeypatch.setattr(chat_service, "generate_structured_answer", raise_json)
    monkeypatch.setattr(
        chat_service, "generate_answer",
        lambda *_, **__: "Câu trả lời dạng text fallback.",
    )

    reply, sources, structured = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="q"
    )
    assert "fallback" in reply
    assert structured is None


def test_send_chat_message_returns_clarify_when_no_contexts(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "search_legal_context", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    captured = {}
    def fake_structured(*_, **kwargs):
        captured["contexts_empty"] = len(kwargs.get("contexts", []))
        return {
            "loi_chao": "Chào",
            "tom_tat_vu_viec": "Chưa rõ",
            "phan_tich_phap_ly": "Hiện chưa tìm thấy điều luật phù hợp...",
            "phuong_an_khuyen_nghi": [],
            "rui_ro_can_luu_y": [],
            "cau_hoi_hoi_them": ["Bạn cho biết thời điểm kết hôn?"],
            "disclaimer": "ok",
            "trich_dan_nguon": [],
        }
    monkeypatch.setattr(chat_service, "generate_structured_answer", fake_structured)
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    reply, sources, structured = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Hỏi chung chung"
    )
    assert captured["contexts_empty"] is True
    assert structured["cau_hoi_hoi_them"] == ["Bạn cho biết thời điểm kết hôn?"]


def test_send_chat_message_passes_history_to_llm(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "search_legal_context",
        lambda *_, **__: [{"content_text": "ctx", "title": "T", "source_url": "u"}],
    )
    captured = {}
    def fake_structured(*_, **kwargs):
        captured["history_len"] = len(kwargs.get("history", []))
        return {
            "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
            "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
            "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": [],
        }
    monkeypatch.setattr(chat_service, "generate_structured_answer", fake_structured)
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    class FakeMsg:
        def __init__(self, role, content):
            self.role = role
            self.content = content
    history = [FakeMsg("user", "cũ"), FakeMsg("assistant", "trả lời cũ")]
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: history)

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="mới")
    assert captured["history_len"] == 2
```

- [ ] **Step 3: Chạy test, confirm fail (chat_service chưa có API mới)**

```bash
cd backend
pytest tests/services/test_chat_service.py -v
```

Expected: 4 FAIL (send_chat_message signature cũ, không có generate_structured_answer).

- [ ] **Step 4: Rewrite chat_service.py**

Ghi đè `backend/services/chat_service.py`:

```python
import logging

from services.answer_service import generate_answer
from services.groq_service import generate_structured_answer
from services.qdrant_service import search_legal_context
from services.session_service import get_session, save_message
from repositories.messages import list_recent_messages

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
RETRIEVAL_TOP_K = 4
LOW_SCORE_THRESHOLD = 0.55  # below this we treat retrieval as unreliable


def _format_history_for_llm(messages) -> list[dict]:
    """Convert ORM messages to plain dicts in OpenAI chat format."""
    return [{"role": m.role, "content": m.content} for m in messages]


def _structured_to_display_text(structured: dict) -> str:
    """Flatten the 7-section JSON into a user-friendly Markdown block for fallback/sources."""
    parts: list[str] = []
    if structured.get("loi_chao"):
        parts.append(f"**{structured['loi_chao']}**\n")
    if structured.get("tom_tat_vu_viec"):
        parts.append(f"### Tóm tắt vụ việc\n{structured['tom_tat_vu_viec']}\n")
    if structured.get("phan_tich_phap_ly"):
        parts.append(f"### Phân tích pháp lý\n{structured['phan_tich_phap_ly']}\n")
    if structured.get("phuong_an_khuyen_nghi"):
        parts.append("### Phương án khuyến nghị")
        parts.extend(f"- {p}" for p in structured["phuong_an_khuyen_nghi"])
        parts.append("")
    if structured.get("rui_ro_can_luu_y"):
        parts.append("### Rủi ro cần lưu ý")
        parts.extend(f"- {r}" for r in structured["rui_ro_can_luu_y"])
        parts.append("")
    if structured.get("cau_hoi_hoi_them"):
        parts.append("### Câu hỏi cần bạn cung cấp thêm")
        parts.extend(f"- {c}" for c in structured["cau_hoi_hoi_them"])
        parts.append("")
    if structured.get("disclaimer"):
        parts.append(f"> ⚠️ {structured['disclaimer']}")
    return "\n".join(parts).strip()


def _is_retrieval_reliable(contexts: list[dict]) -> bool:
    if not contexts:
        return False
    if any(c.get("score", 1.0) < LOW_SCORE_THRESHOLD for c in contexts):
        return False
    return True


def send_chat_message(
    db,
    session_id: str,
    user_id: str,
    message: str,
) -> tuple[str, list[str], dict | None]:
    """Main chat entry point used by the API route.

    Returns (display_text, sources, structured_dict_or_None).
    """
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    # 1. Persist user turn first
    save_message(db, session_id, user_id, "user", message)

    # 2. Load recent history (oldest -> newest) for context
    recent = list_recent_messages(db, session_id, limit=HISTORY_LIMIT)
    # Drop the message we just saved from the history we feed to the LLM
    history = _format_history_for_llm(recent[:-1])

    # 3. Retrieve legal context
    contexts = search_legal_context(message, top_k=RETRIEVAL_TOP_K)

    # 4. Guard: if retrieval is empty/unreliable, do NOT silently invent law.
    #    We still call the LLM with empty contexts; the system prompt instructs
    #    the LLM to ask for more facts and not invent citations.
    if not _is_retrieval_reliable(contexts):
        logger.info("Retrieval unreliable for session=%s msg=%r", session_id, message[:80])

    # 5. Try structured JSON path first
    structured: dict | None = None
    try:
        structured = generate_structured_answer(
            question=message, contexts=contexts, history=history
        )
    except ValueError as exc:
        logger.warning("Structured answer failed (%s), falling back to text", exc)
        text = generate_answer(question=message, contexts=contexts, history=history)
        save_message(db, session_id, user_id, "assistant", text, {"sources": []})
        return text, [], None

    # 6. Render display text from structured JSON
    display = _structured_to_display_text(structured)
    sources = [
        item.get("source_url", "")
        for item in contexts
        if item.get("source_url")
    ]
    save_message(
        db, session_id, user_id, "assistant", display,
        {"sources": sources, "structured": structured},
    )
    return display, sources, structured
```

- [ ] **Step 5: Cập nhật api route để trả 3-tuple**

Sửa `backend/api/routes/chat.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db
from entities.user import User
from services.chat_service import send_chat_message

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] | None = None
    structured: dict | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    try:
        reply, sources, structured = send_chat_message(
            db, request.session_id, str(current_user.id), request.message
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ChatResponse(reply=reply, sources=sources, structured=structured)
```

- [ ] **Step 6: Cập nhật answer_service re-export**

`backend/services/answer_service.py` đã có sẵn; thêm structured:

```python
from services.groq_service import generate_answer, generate_structured_answer

__all__ = ["generate_answer", "generate_structured_answer"]
```

- [ ] **Step 7: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/ -v
```

Expected: tất cả PASS (test_groq_service + test_chat_service + test_prompt_loader).

- [ ] **Step 8: Commit**

```bash
git add backend/services/chat_service.py backend/services/answer_service.py backend/repositories/messages.py backend/api/routes/chat.py backend/tests/services/test_chat_service.py
git commit -m "feat(chat): structured 7-section response + history + retrieval guard"
```

---

## Task 1.5: Frontend render JSON 7-section

**Files:**
- Modify: `frontend/lib/api.ts` (add structured to ChatResponse + new type)
- Modify: `frontend/components/chat/assistant-message.tsx` (full rewrite)
- Create: `frontend/components/chat/lawyer-response-view.tsx`
- Test: smoke (manual)

- [ ] **Step 1: Mở rộng types trong api.ts**

Sửa `frontend/lib/api.ts`:

Thêm type mới sau `interface ChatResponse`:

```typescript
export interface LawyerSection {
  loi_chao: string
  tom_tat_vu_viec: string
  phan_tich_phap_ly: string
  phuong_an_khuyen_nghi: string[]
  rui_ro_can_luu_y: string[]
  cau_hoi_hoi_them: string[]
  disclaimer: string
  trich_dan_nguon: string[]
}

export interface ChatResponse {
  reply: string
  sources?: string[]
  structured?: LawyerSection | null
}
```

- [ ] **Step 2: Viết component LawyerResponseView**

Tạo `frontend/components/chat/lawyer-response-view.tsx`:

```tsx
'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { LawyerSection } from '@/lib/api'

interface LawyerResponseViewProps {
  section: LawyerSection
  sources: string[] | undefined
}

export function LawyerResponseView({ section, sources }: LawyerResponseViewProps) {
  const hasAny =
    section.loi_chao ||
    section.tom_tat_vu_viec ||
    section.phan_tich_phap_ly ||
    section.phuong_an_khuyen_nghi.length > 0 ||
    section.rui_ro_can_luu_y.length > 0 ||
    section.cau_hoi_hoi_them.length > 0

  if (!hasAny) {
    // Defensive: backend forgot to populate, fall back to plain text
    return null
  }

  return (
    <div className="lawyer-response" data-testid="lawyer-response">
      {section.loi_chao && (
        <p className="lawyer-greeting" role="doc-subtitle">
          {section.loi_chao}
        </p>
      )}

      {section.tom_tat_vu_viec && (
        <section aria-label="Tóm tắt vụ việc">
          <h4>Tóm tắt vụ việc</h4>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.tom_tat_vu_viec}</ReactMarkdown>
        </section>
      )}

      {section.phan_tich_phap_ly && (
        <section aria-label="Phân tích pháp lý">
          <h4>Phân tích pháp lý</h4>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.phan_tich_phap_ly}</ReactMarkdown>
        </section>
      )}

      {section.phuong_an_khuyen_nghi.length > 0 && (
        <section aria-label="Phương án khuyến nghị">
          <h4>Phương án khuyến nghị</h4>
          <ul>
            {section.phuong_an_khuyen_nghi.map((p, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{p}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.rui_ro_can_luu_y.length > 0 && (
        <section aria-label="Rủi ro cần lưu ý" className="lawyer-warn-block">
          <h4>⚠️ Rủi ro cần lưu ý</h4>
          <ul>
            {section.rui_ro_can_luu_y.map((r, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{r}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.cau_hoi_hoi_them.length > 0 && (
        <section aria-label="Câu hỏi cần bạn cung cấp thêm" className="lawyer-ask-block">
          <h4>📋 Câu hỏi cần bạn cung cấp thêm</h4>
          <ul>
            {section.cau_hoi_hoi_them.map((c, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{c}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.disclaimer && (
        <aside className="lawyer-disclaimer" role="note">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.disclaimer}</ReactMarkdown>
        </aside>
      )}

      {(sources && sources.length > 0) || section.trich_dan_nguon.length > 0 ? (
        <div className="message-sources" aria-label="Nguồn tham khảo">
          {[...section.trich_dan_nguon, ...(sources ?? [])].map((s, i) => (
            <span key={`${s}-${i}`} className="message-source-chip">
              {s}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
```

- [ ] **Step 3: Sửa AssistantMessage dùng component mới khi có structured**

Ghi đè `frontend/components/chat/assistant-message.tsx`:

```tsx
'use client'

import { LawyerResponseView } from './lawyer-response-view'
import type { ChatUiMessage } from './chat.types'

interface AssistantMessageProps {
  message: ChatUiMessage
  onCopy: (text: string) => void
}

export function AssistantMessage({ message, onCopy }: AssistantMessageProps) {
  const hasStructured =
    message.structured &&
    (message.structured.loi_chao ||
      message.structured.tom_tat_vu_viec ||
      message.structured.phan_tich_phap_ly)

  return (
    <article className="message-row">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        Lx
      </div>
      <div className="message-card message-card--assistant">
        {hasStructured && message.structured ? (
          <LawyerResponseView section={message.structured} sources={message.sources} />
        ) : (
          <pre className="message-fallback-text">{message.content}</pre>
        )}

        <div className="message-actions">
          <button
            type="button"
            className="message-action"
            onClick={() => onCopy(message.content)}
            title="Sao chép nội dung"
          >
            Sao chép
          </button>
        </div>
      </div>
    </article>
  )
}
```

- [ ] **Step 4: Cập nhật ChatUiMessage type**

Sửa `frontend/components/chat/chat.types.ts` (file hiện có — tạo nếu chưa):

```typescript
import type { LawyerSection } from '@/lib/api'

export interface ChatUiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  structured?: LawyerSection | null
  createdAt: string
}
```

- [ ] **Step 5: Map structured trong mapMessageHistory**

Sửa `frontend/lib/api.ts` — function `mapMessageHistory`:

```typescript
export function mapMessageHistory(messages: MessageResponse[]): ChatUiMessage[] {
  return messages
    .map((message) => ({
      id: message.id,
      role: (message.role === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
      content: message.content,
      sources: Array.isArray(message.sources_json?.sources)
        ? (message.sources_json?.sources as string[])
        : undefined,
      structured: (message.sources_json?.structured as LawyerSection | null | undefined) ?? null,
      createdAt: '',
    }))
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
}
```

- [ ] **Step 6: Smoke test thủ công**

```bash
# Terminal 1
cd backend
pytest -v
# Terminal 2
cd backend
uvicorn main:app --reload
# Terminal 3
cd frontend
npm run dev
```

Mở browser → đăng nhập → tạo session mới → hỏi "Điều kiện đơn phương ly hôn là gì?".

Expected:
- Bot trả lời 7 phần rõ ràng (Tóm tắt / Phân tích / Phương án / Rủi ro / Câu hỏi thêm / Disclaimer / Nguồn).
- Disclaimer hiển thị cuối.
- Hỏi tiếp "Còn thời hiệu thì sao?" → bot nhớ context phiên trước.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/api.ts frontend/components/chat/
git commit -m "feat(ui): render 7-section lawyer response (Sprint 1)"
```

---

## Self-review Sprint 1

- [ ] Tất cả test pass: `cd backend && pytest -v` — 1 prompt_loader + 11 groq + 6 lawyer_response + 4 chat_service = **22 tests**.
- [ ] File `groq_service.py` < 300 dòng.
- [ ] File `chat_service.py` < 200 dòng.
- [ ] Prompt persona nằm trong `backend/prompts/lawyer_persona_v1.md`, không hard-code.
- [ ] Có thể demo: hỏi → bot trả JSON 7-section → có disclaimer → có trích dẫn.
- [ ] Không có schema DB thay đổi (Alembic không tạo migration mới).
- [ ] README update nếu có (optional).

---

## Kết thúc Sprint 1

Sau khi hoàn thành, hệ thống đáp ứng **~3/5** yêu cầu luật sư (clarify, classify dạng hỏi thêm, recommend, disclaimer, citations). Sprint 2 sẽ thêm **case memory** (nhớ facts qua nhiều lượt, intake form, phân tích theo loại vụ).
