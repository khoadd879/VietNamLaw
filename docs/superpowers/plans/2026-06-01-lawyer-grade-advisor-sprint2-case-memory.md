# Sprint 2 — Case Memory (case_facts + summary + two-stage reasoning + intake)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến chatbot từ "luật sư có persona" thành **luật sư có hồ sơ** — nhớ được facts của vụ việc xuyên suốt phiên, tự extract facts mới từ mỗi lượt user, hỏi intake khi mở phiên mới, hai giai đoạn suy luận (extract → synthesize) để phân tích theo đúng loại vụ.

**Architecture:** Thêm schema `case_facts` (1 row / fact) + 3 cột trên `chat_sessions` (`case_type`, `case_summary`, `conversation_phase`). Service `fact_extractor` LLM-call riêng (cheap model, temperature 0) parse user message → facts. Service `two_stage_reasoner` orchestrator: gọi extractor trước, update case_facts, build "case_brief" gồm facts + summary, rồi gọi synthesizer với case_brief thay vì chỉ history. Frontend intake form xuất hiện khi session mới chưa có `intake_completed_at`. Prompt files mới: `fact_extractor_v1.md`, `synthesizer_v1.md`.

**Tech Stack:** Same. Thêm: Alembic migration cho schema mới, Pydantic models cho CaseFact và CaseBrief, Next.js form component (controlled inputs).

**Phụ thuộc:** Sprint 1 (system prompt + structured output đã chạy). Sprint 2 không đụng Sprint 3.

---

## Task 2.1: Alembic migration cho case_facts + cột mới trên chat_sessions

**Files:**
- Create: `backend/entities/case_fact.py`
- Modify: `backend/entities/chat_session.py` (thêm 4 cột)
- Modify: `backend/alembic/env.py` (import entity mới)
- Create: `backend/alembic/versions/<hash>_add_case_facts_and_session_columns.py`
- Test: `backend/tests/entities/test_case_fact.py`

- [ ] **Step 1: Tạo entity CaseFact**

Ghi `backend/entities/case_fact.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class CaseFact(Base):
    """A single fact extracted from a user message within a chat session.

    Examples:
        - "Ngày kết hôn: 2018-03-15"
        - "Có con chung: 1 (3 tuổi)"
        - "Tài sản chung: căn hộ quận 2, ô tô"
    """

    __tablename__ = "case_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(128), nullable=False)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chat_messages.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 2: Thêm 4 cột mới vào ChatSession**

Sửa `backend/entities/chat_session.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    case_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    case_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_phase: Mapped[str] = mapped_column(String(32), default="intake", nullable=False)
    intake_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 3: Đăng ký entity mới trong alembic env.py**

Sửa `backend/alembic/env.py`, thêm import:

```python
from entities.case_fact import CaseFact
from entities.chat_session import ChatSession
from entities.chat_message import ChatMessage
from entities.user import User
```

- [ ] **Step 4: Viết failing test cho entity**

Ghi `backend/tests/entities/test_case_fact.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from entities.case_fact import CaseFact
from entities.chat_session import ChatSession
from entities.user import User


def test_case_fact_table_created_and_columns_present() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert "case_facts" in Base.metadata.tables
    cols = {c.name for c in Base.metadata.tables["case_facts"].columns}
    for required in {"id", "session_id", "user_id", "fact_key", "fact_value", "confidence", "created_at", "updated_at"}:
        assert required in cols, f"missing column {required}"


def test_chat_session_has_new_columns() -> None:
    cols = {c.name for c in Base.metadata.tables["chat_sessions"].columns}
    for required in {"case_type", "case_summary", "conversation_phase", "intake_completed_at"}:
        assert required in cols


def test_case_fact_round_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        u = User(id="u1", email="a@b.c", password_hash="x")
        s = ChatSession(id="s1", user_id="u1", title="t")
        db.add_all([u, s])
        db.commit()
        f = CaseFact(id="f1", session_id="s1", user_id="u1", fact_key="ngay_ket_hon", fact_value="2018-03-15")
        db.add(f)
        db.commit()
        db.refresh(f)
        assert f.fact_key == "ngay_ket_hon"
        assert f.confidence == 1.0
```

- [ ] **Step 5: Chạy test, confirm pass**

```bash
cd backend
pytest tests/entities/test_case_fact.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Tạo Alembic migration**

```bash
cd backend
alembic revision --autogenerate -m "add case_facts and chat_session case columns"
```

Sau đó **kiểm tra file migration được sinh ra** tại `backend/alembic/versions/`, đảm bảo:
- Có `op.create_table("case_facts", ...)` với đầy đủ cột.
- Có `op.add_column("chat_sessions", ...)` cho 4 cột mới.
- Có default value cho `conversation_phase` = `'intake'`.

Nếu autogenerate không bắt được (do SQLite limitation), sửa tay theo template:

```python
"""add case_facts and chat_session case columns

Revision ID: <hash>
Revises: 13118a35765c
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "<hash>"
down_revision = "13118a35765c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_facts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("chat_sessions.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fact_key", sa.String(length=128), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), sa.ForeignKey("chat_messages.id"), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("chat_sessions", sa.Column("case_type", sa.String(length=64), nullable=True))
    op.create_index("ix_chat_sessions_case_type", "chat_sessions", ["case_type"])
    op.add_column("chat_sessions", sa.Column("case_summary", sa.Text(), nullable=True))
    op.add_column("chat_sessions", sa.Column("conversation_phase", sa.String(length=32), nullable=False, server_default="intake"))
    op.add_column("chat_sessions", sa.Column("intake_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "intake_completed_at")
    op.drop_column("chat_sessions", "conversation_phase")
    op.drop_column("chat_sessions", "case_summary")
    op.drop_index("ix_chat_sessions_case_type", table_name="chat_sessions")
    op.drop_column("chat_sessions", "case_type")
    op.drop_table("case_facts")
```

- [ ] **Step 7: Chạy migration trên Neon dev**

```bash
cd backend
NEON_DATABASE_URL=<your-neon-dev-url> alembic upgrade head
NEON_DATABASE_URL=<your-neon-dev-url> alembic current
```

Expected: `alembic current` in ra hash mới.

- [ ] **Step 8: Commit**

```bash
git add backend/entities/case_fact.py backend/entities/chat_session.py backend/alembic/env.py backend/alembic/versions/ backend/tests/entities/test_case_fact.py
git commit -m "feat(db): add case_facts table + case columns on chat_sessions"
```

---

## Task 2.2: Repository + service cho CaseFact CRUD

**Files:**
- Create: `backend/repositories/case_facts.py`
- Modify: `backend/services/session_service.py` (thêm 4 helper)
- Test: `backend/tests/repositories/test_case_facts.py`

- [ ] **Step 1: Tạo repository**

Ghi `backend/repositories/case_facts.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from entities.case_fact import CaseFact


def upsert_fact(
    db: Session,
    fact_id: str,
    session_id: str,
    user_id: str,
    fact_key: str,
    fact_value: str,
    source_message_id: str | None = None,
    confidence: float = 1.0,
) -> CaseFact:
    """Insert a fact, or update if (session_id, fact_key) already exists."""
    existing = db.execute(
        select(CaseFact).where(
            CaseFact.session_id == session_id,
            CaseFact.fact_key == fact_key,
        )
    ).scalar_one_or_none()

    from datetime import datetime
    now = datetime.utcnow()
    if existing is None:
        fact = CaseFact(
            id=fact_id,
            session_id=session_id,
            user_id=user_id,
            fact_key=fact_key,
            fact_value=fact_value,
            source_message_id=source_message_id,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        db.add(fact)
    else:
        existing.fact_value = fact_value
        existing.source_message_id = source_message_id
        existing.confidence = confidence
        existing.updated_at = now
        fact = existing
    db.commit()
    return fact


def list_facts_for_session(db: Session, session_id: str) -> list[CaseFact]:
    return db.execute(
        select(CaseFact).where(CaseFact.session_id == session_id).order_by(CaseFact.created_at.asc())
    ).scalars().all()


def delete_facts_for_session(db: Session, session_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    db.execute(sql_delete(CaseFact).where(CaseFact.session_id == session_id))
    db.commit()
```

- [ ] **Step 2: Mở rộng session_service**

Sửa `backend/services/session_service.py`, thêm cuối file (trước các import `from repositories` hiện có vẫn giữ nguyên):

Thêm import ở đầu file:

```python
from datetime import datetime
from entities.case_fact import CaseFact
from repositories.case_facts import list_facts_for_session, upsert_fact
```

Thêm functions mới:

```python
def get_or_create_session(db, user_id: str, title: str | None = None) -> ChatSession:
    """Alias for create_session; clearer name for intake flow."""
    return create_session(db, user_id, title)


def update_session_case(
    db,
    session_id: str,
    user_id: str,
    case_type: str | None = None,
    case_summary: str | None = None,
    conversation_phase: str | None = None,
    intake_completed_at: datetime | None = None,
) -> ChatSession | None:
    session = get_session_for_user(db, session_id, user_id)
    if session is None:
        return None
    if case_type is not None:
        session.case_type = case_type
    if case_summary is not None:
        session.case_summary = case_summary
    if conversation_phase is not None:
        session.conversation_phase = conversation_phase
    if intake_completed_at is not None:
        session.intake_completed_at = intake_completed_at
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def add_fact(
    db,
    session_id: str,
    user_id: str,
    fact_key: str,
    fact_value: str,
    source_message_id: str | None = None,
    confidence: float = 1.0,
) -> CaseFact:
    from uuid import uuid4
    return upsert_fact(
        db,
        fact_id=str(uuid4()),
        session_id=session_id,
        user_id=user_id,
        fact_key=fact_key,
        fact_value=fact_value,
        source_message_id=source_message_id,
        confidence=confidence,
    )


def list_case_facts(db, session_id: str) -> list[CaseFact]:
    return list_facts_for_session(db, session_id)
```

- [ ] **Step 3: Viết failing test**

Ghi `backend/tests/repositories/test_case_facts.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from entities.case_fact import CaseFact
from entities.chat_session import ChatSession
from entities.user import User
from repositories.case_facts import list_facts_for_session, upsert_fact


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _seed(db):
    db.add_all([
        User(id="u1", email="a@b.c", password_hash="x"),
        ChatSession(id="s1", user_id="u1", title="t"),
    ])
    db.commit()


def test_upsert_fact_inserts_new_row() -> None:
    db = _make_db()
    _seed(db)
    f = upsert_fact(db, "f1", "s1", "u1", "ngay_ket_hon", "2018-03-15")
    assert f.id == "f1"
    rows = list_facts_for_session(db, "s1")
    assert len(rows) == 1
    assert rows[0].fact_key == "ngay_ket_hon"


def test_upsert_fact_updates_existing_row_with_same_key() -> None:
    db = _make_db()
    _seed(db)
    upsert_fact(db, "f1", "s1", "u1", "ngay_ket_hon", "2018-03-15")
    f2 = upsert_fact(db, "f2", "s1", "u1", "ngay_ket_hon", "2020-05-01")
    rows = list_facts_for_session(db, "s1")
    assert len(rows) == 1
    assert rows[0].fact_value == "2020-05-01"
    assert rows[0].id == "f2"
```

- [ ] **Step 4: Chạy test, confirm pass**

```bash
cd backend
pytest tests/repositories/test_case_facts.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/repositories/case_facts.py backend/services/session_service.py backend/tests/repositories/test_case_facts.py
git commit -m "feat(repo): CaseFact upsert + session case update helpers"
```

---

## Task 2.3: Fact extractor service + prompt

**Files:**
- Create: `backend/prompts/fact_extractor_v1.md`
- Create: `backend/services/fact_extractor.py`
- Test: `backend/tests/services/test_fact_extractor.py`

- [ ] **Step 1: Tạo prompt file**

Ghi `backend/prompts/fact_extractor_v1.md`:

```markdown
# Nhiệm vụ
Bạn là trợ lý AI trích xuất **facts pháp lý** từ câu nói của người dùng Việt Nam.

# Input
Bạn nhận:
1. `existing_facts`: danh sách facts đã biết (key-value).
2. `new_message`: câu user vừa gửi.
3. `case_type_hint` (optional): gợi ý loại vụ (ví dụ "hôn nhân gia đình", "lao động", "đất đai").

# Output — JSON thuần, không markdown fence
```json
{
  "case_type": "hôn nhân gia đình" | "lao động" | "đất đai" | "hợp đồng" | "hình sự" | "hành chính" | "thừa kế" | "sở hữu trí tuệ" | "khác" | null,
  "extracted_facts": [
    {
      "key": "ngay_ket_hon",
      "value": "2018-03-15",
      "confidence": 0.95
    }
  ],
  "case_summary": "Tóm tắt 1-2 câu về vụ việc dựa trên facts đã biết và message mới, hoặc null nếu quá ít thông tin."
}
```

# Quy tắc trích xuất
1. **Key dùng snake_case tiếng Việt không dấu.** Ví dụ: `ngay_ket_hon`, `so_con_chung`, `tai_san_chung`, `muc_luong`, `hop_dong_so`, `thoi_han_thue`.
2. **Chỉ trích facts có giá trị pháp lý rõ ràng**, bỏ qua small talk ("chào bạn", "cảm ơn").
3. **Không suy luận.** Nếu user nói "chúng tôi cãi nhau nhiều" → KHÔNG tự suy ra `ly_do = trầm_trọng`. Chỉ ghi `ton_tai_tranh_chap = true`.
4. **Confidence từ 0.0 đến 1.0.** 1.0 = user nói rõ ràng. 0.5 = user ngụ ý.
5. **Cập nhật facts cũ**: nếu user cho biết thông tin mới thay thế fact cũ (ví dụ đã nói kết hôn 2018, giờ nói 2020), trả về fact mới với cùng `key` — backend sẽ upsert.
6. **Không trùng key**: nếu một message chứa 2 giá trị cùng key, lấy giá trị user nhấn mạnh gần nhất.
7. **Nếu message không chứa fact mới**, trả `extracted_facts: []` và `case_summary: null`.
8. **case_type** chỉ thay đổi khi có đủ bằng chứng rõ ràng, không đoán từ 1 message.
```

- [ ] **Step 2: Tạo service**

Ghi `backend/services/fact_extractor.py`:

```python
import json
import logging
import re
from typing import Any

from services.groq_service import _run_pooled
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

FACT_EXTRACTOR_PROMPT = "fact_extractor_v1"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(s: str) -> str:
    return _FENCE_RE.sub("", s).strip()


def extract_facts(
    message: str,
    existing_facts: list[dict[str, Any]] | None = None,
    case_type_hint: str | None = None,
) -> dict:
    """Call LLM and return parsed JSON: {case_type, extracted_facts, case_summary}.

    Falls back to a safe empty result if the LLM returns invalid JSON.
    Never raises — extractor is best-effort.
    """
    system_prompt = load_prompt(FACT_EXTRACTOR_PROMPT)
    user_payload = {
        "existing_facts": existing_facts or [],
        "new_message": message,
        "case_type_hint": case_type_hint,
    }
    user_text = json.dumps(user_payload, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    raw = _run_pooled(
        messages,
        response_format={"type": "json_object"},
        empty_fallback="",
    )
    if not raw:
        return {"case_type": None, "extracted_facts": [], "case_summary": None}
    cleaned = _strip_code_fence(raw)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Fact extractor returned invalid JSON: %r (%s)", raw[:200], exc)
        return {"case_type": None, "extracted_facts": [], "case_summary": None}
    return {
        "case_type": result.get("case_type"),
        "extracted_facts": result.get("extracted_facts") or [],
        "case_summary": result.get("case_summary"),
    }
```

- [ ] **Step 3: Viết failing test**

Ghi `backend/tests/services/test_fact_extractor.py`:

```python
from types import SimpleNamespace
from unittest.mock import patch

from services import fact_extractor
from services.fact_extractor import extract_facts


def make_response(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_extract_facts_parses_well_formed_json() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = json.dumps({
            "case_type": "hôn nhân gia đình",
            "extracted_facts": [
                {"key": "ngay_ket_hon", "value": "2018-03-15", "confidence": 0.95}
            ],
            "case_summary": "User kết hôn năm 2018.",
        })
        result = extract_facts("Tôi kết hôn ngày 15/3/2018")
    assert result["case_type"] == "hôn nhân gia đình"
    assert result["extracted_facts"][0]["key"] == "ngay_ket_hon"
    assert result["extracted_facts"][0]["confidence"] == 0.95


def test_extract_facts_returns_empty_on_invalid_json() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = "not json {"
        result = extract_facts("xin chào")
    assert result == {"case_type": None, "extracted_facts": [], "case_summary": None}


def test_extract_facts_returns_empty_on_empty_response() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = ""
        result = extract_facts("ok")
    assert result["extracted_facts"] == []


def test_extract_facts_passes_existing_facts_and_hint_to_llm() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = '{"case_type": null, "extracted_facts": [], "case_summary": null}'
        extract_facts(
            "thêm nữa là tôi có 1 con",
            existing_facts=[{"key": "ngay_ket_hon", "value": "2018"}],
            case_type_hint="hôn nhân gia đình",
        )
    messages = mock.call_args.args[0]
    user_text = messages[1]["content"]
    import json as _json
    payload = _json.loads(user_text)
    assert payload["existing_facts"] == [{"key": "ngay_ket_hon", "value": "2018"}]
    assert payload["case_type_hint"] == "hôn nhân gia đình"
    assert payload["new_message"] == "thêm nữa là tôi có 1 con"


def test_extract_facts_uses_json_response_format() -> None:
    with patch("services.fact_extractor._run_pooled") as mock:
        mock.return_value = '{"case_type": null, "extracted_facts": [], "case_summary": null}'
        extract_facts("m")
    assert mock.call_args.kwargs["response_format"] == {"type": "json_object"}


# Need json imported in test scope
import json
```

- [ ] **Step 4: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_fact_extractor.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/prompts/fact_extractor_v1.md backend/services/fact_extractor.py backend/tests/services/test_fact_extractor.py
git commit -m "feat(extractor): LLM-based fact extractor service with prompt"
```

---

## Task 2.4: Synthesizer prompt + two-stage reasoner

**Files:**
- Create: `backend/prompts/synthesizer_v1.md`
- Create: `backend/services/two_stage_reasoner.py`
- Modify: `backend/services/chat_service.py` (orchestrate two-stage)
- Test: `backend/tests/services/test_two_stage_reasoner.py`

- [ ] **Step 1: Tạo synthesizer prompt**

Ghi `backend/prompts/synthesizer_v1.md`:

```markdown
# Vai trò
Bạn là **luật sư tư vấn pháp luật Việt Nam** đang có hồ sơ vụ việc (case brief) đầy đủ. Bạn sẽ trả lời câu hỏi tư vấn tiếp theo dựa trên hồ sơ + lịch sử hội thoại + ngữ cảnh pháp lý.

# Quy tắc persona (giống persona gốc)
- Tiếng Việt.
- Không bịa điều luật — chỉ dùng trong NGỮ CẢNH PHÁP LÝ.
- Có disclaimer cuối.
- Hỏi thêm facts nếu hồ sơ còn thiếu.
- Cảnh báo rủi ro (thời hiệu, chi phí, bằng chứng).

# Input bạn nhận
1. `CASE_BRIEF`: hồ sơ vụ việc (case_type, case_summary, danh sách facts key-value).
2. `LỊCH SỬ HỘI THOẠI` (nếu có).
3. `NGỮ CẢNH PHÁP LÝ` (chunks từ cơ sở dữ liệu pháp luật, có thể rỗng).
4. `CÂU HỎI / YÊU CẦU TƯ VẤN HIỆN TẠI`.

# Output format (JSON thuần, không markdown fence)
```json
{
  "loi_chao": "...",
  "tom_tat_vu_viec": "...",  // dựa trên CASE_BRIEF
  "phân_tích_pháp_lý": "...",
  "phuong_an_khuyen_nghi": ["..."],
  "rui_ro_can_luu_y": ["..."],
  "cau_hoi_hoi_them": ["..."],
  "disclaimer": "Đây là tư vấn pháp luật mang tính tham khảo, không thay thế ý kiến luật sư hành nghề cụ thể cho hồ sơ của bạn. Trường hợp phức tạp, bạn nên liên hệ luật sư/Văn phòng luật sư/Luật sư đoàn tại địa phương.",
  "trich_dan_nguon": ["..."]
}
```

# Nguyên tắc phân tích theo loại vụ
- **Hôn nhân gia đình**: ưu tiên quyền lợi con chung, thời hiện 2 năm kể từ ly hôn, phân chia tài sản chung vs tài sản riêng.
- **Lao động**: hợp đồng lao động (thử việc, xác định thời hạn, không xác định thời hạn), đơn phương chấm dứt HĐ (thông báo trước 30-45 ngày), trợ cấp thôi việc.
- **Đất đai**: thời hạn sử dụng, quyền sử dụng, tranh chấp ranh giới, thủ tục hành chính.
- **Hợp đồng**: điều kiện có hiệu lực, vi phạm, bồi thường thiệt hại, thời hiệu khởi kiện 3 năm (Bộ luật Dân sự 2015).
- **Thừa kế**: hàng thừa kế, thời hiệu, di sản chung vs riêng.
- **Hình sự**: KHÔNG tư vấn chi tiết — khuyên liên hệ luật sư hình sự ngay.

# Nếu CASE_BRIEF quá thiếu
Nếu `cau_hoi_hoi_them` nên chứa 2-4 câu hỏi facts cốt lõi còn thiếu để phân tích.
```

- [ ] **Step 2: Tạo two_stage_reasoner**

Ghi `backend/services/two_stage_reasoner.py`:

```python
"""Two-stage reasoning: extract facts first, then synthesize with case brief."""
import logging
from typing import Any

from services.fact_extractor import extract_facts
from services.groq_service import generate_structured_answer
from services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

SYNTHESIZER_PROMPT = "synthesizer_v1"


def _build_case_brief(case_type: str | None, case_summary: str | None, facts: list) -> dict:
    return {
        "case_type": case_type,
        "case_summary": case_summary,
        "facts": [{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in facts],
    }


def _format_case_brief_for_llm(brief: dict) -> str:
    lines = ["CASE_BRIEF:"]
    lines.append(f"- case_type: {brief['case_type'] or '(chưa rõ)'}")
    lines.append(f"- case_summary: {brief['case_summary'] or '(chưa có)'}")
    if brief["facts"]:
        lines.append("- facts:")
        for f in brief["facts"]:
            lines.append(f"    {f['key']}: {f['value']} (confidence={f['confidence']:.2f})")
    else:
        lines.append("- facts: (rỗng)")
    return "\n".join(lines)


def _format_context_chunks(contexts: list[dict]) -> list[str]:
    return [
        f"[{c.get('title', 'Văn bản pháp luật')}]\n{c.get('content_text', '')}"
        for c in contexts
    ]


def _build_synth_user_message(case_brief: dict, contexts: list[dict], question: str) -> str:
    parts = [_format_case_brief_for_llm(case_brief), ""]
    parts.append("NGỮ CẢNH PHÁP LÝ:")
    chunks = _format_context_chunks(contexts)
    if chunks:
        parts.extend(chunks)
    else:
        parts.append("(rỗng — không tìm thấy điều luật phù hợp, hãy hỏi user thêm facts)")
    parts.append("")
    parts.append("CÂU HỎI / YÊU CẦU TƯ VẤN HIỆN TẠI:")
    parts.append(question)
    return "\n".join(parts)


def two_stage_reason(
    message: str,
    contexts: list[dict],
    history: list[dict[str, str]] | None,
    existing_facts: list,
    case_type: str | None,
    case_summary: str | None,
) -> dict:
    """Stage 1: extract facts. Stage 2: synthesize using updated case brief.

    Returns dict with keys: structured, extracted, updated_case_type, updated_case_summary.
    Does NOT persist anything — caller (chat_service) does that.
    """
    # Stage 1
    extracted = extract_facts(
        message=message,
        existing_facts=[
            {"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence}
            for f in existing_facts
        ],
        case_type_hint=case_type,
    )

    # Build a virtual case brief (NOT yet persisted)
    virtual_brief = _build_case_brief(
        case_type=extracted.get("case_type") or case_type,
        case_summary=extracted.get("case_summary") or case_summary,
        facts=list(existing_facts) + [
            # Pseudo-fact objects for the LLM (not persisted)
            type("PF", (), {
                "fact_key": f["key"], "fact_value": f["value"], "confidence": f["confidence"]
            })()
            for f in extracted.get("extracted_facts", [])
        ],
    )

    # Stage 2
    system_prompt = load_prompt(SYNTHESIZER_PROMPT)
    user_text = _build_synth_user_message(virtual_brief, contexts, message)
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    # We can't directly call _run_pooled from here because it's a private
    # function in groq_service. Use the public generate_structured_answer by
    # passing an empty contexts and history; but the prompt content already has
    # case_brief + contexts. So we need a small adapter.
    from services.groq_service import _run_pooled
    raw = _run_pooled(messages, response_format={"type": "json_object"}, empty_fallback="")
    import json
    if not raw:
        raise ValueError("Synthesizer returned empty")
    structured = json.loads(raw)

    return {
        "structured": structured,
        "extracted": extracted,
        "updated_case_type": extracted.get("case_type") or case_type,
        "updated_case_summary": extracted.get("case_summary") or case_summary,
    }
```

- [ ] **Step 3: Viết failing test**

Ghi `backend/tests/services/test_two_stage_reasoner.py`:

```python
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
    import json

    with patch("services.fact_extractor.extract_facts", return_value=extracted) as mock_extract, \
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
    import json
    captured = {}
    def fake_run(messages, **kwargs):
        captured["user_text"] = messages[-1]["content"]
        return json.dumps({
            "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
            "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
            "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
        })
    with patch("services.fact_extractor.extract_facts", return_value=extracted), \
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
```

- [ ] **Step 4: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/test_two_stage_reasoner.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/prompts/synthesizer_v1.md backend/services/two_stage_reasoner.py backend/tests/services/test_two_stage_reasoner.py
git commit -m "feat(reasoner): two-stage extract-then-synthesize with case brief"
```

---

## Task 2.5: Orchestrate two-stage trong chat_service + persist facts

**Files:**
- Modify: `backend/services/chat_service.py` (full rewrite)
- Test: `backend/tests/services/test_chat_service.py` (extend)

- [ ] **Step 1: Viết failing test cho case-memory integration**

Sửa `backend/tests/services/test_chat_service.py` — thêm 3 test mới ở cuối file:

```python
def test_chat_persists_extracted_facts(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "search_legal_context", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])

    extracted = {
        "case_type": "hôn nhân gia đình",
        "extracted_facts": [{"key": "ngay_ket_hon", "value": "2018", "confidence": 0.9}],
        "case_summary": "User kết hôn 2018.",
    }
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào", "tom_tat_vu_viec": "ok", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": extracted,
            "updated_case_type": "hôn nhân gia đình",
            "updated_case_summary": "User kết hôn 2018.",
        },
    )

    saved_facts = []
    def fake_add_fact(db, session_id, user_id, fact_key, fact_value, **kwargs):
        saved_facts.append((fact_key, fact_value))
        return object()
    monkeypatch.setattr(chat_service, "add_fact", fake_add_fact)

    case_updates = []
    def fake_update_session_case(db, session_id, user_id, **kwargs):
        case_updates.append(kwargs)
        return object()
    monkeypatch.setattr(chat_service, "update_session_case", fake_update_session_case)
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])

    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="Tôi kết hôn 2018")
    assert ("ngay_ket_hon", "2018") in saved_facts
    assert case_updates[0]["case_type"] == "hôn nhân gia đình"
    assert case_updates[0]["case_summary"] == "User kết hôn 2018."


def test_chat_skips_fact_persist_when_no_extraction(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "search_legal_context", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        },
    )
    add_called = {"flag": False}
    def fake_add_fact(*_, **__):
        add_called["flag"] = True
        return object()
    monkeypatch.setattr(chat_service, "add_fact", fake_add_fact)
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="chào bạn")
    assert add_called["flag"] is False


def test_chat_uses_existing_case_brief_in_two_stage(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "search_legal_context", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])

    class FakeFact:
        def __init__(self, k, v): self.fact_key, self.fact_value, self.confidence = k, v, 1.0
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [FakeFact("ngay_ket_hon", "2018")])

    captured = {}
    def fake_two_stage(**kwargs):
        captured["existing_facts_keys"] = [f.fact_key for f in kwargs["existing_facts"]]
        captured["case_type"] = kwargs["case_type"]
        return {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        }
    monkeypatch.setattr(chat_service, "two_stage_reason", fake_two_stage)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    # Inject case_type/case_summary on the session
    class FakeSession:
        case_type = "hôn nhân gia đình"
        case_summary = "User kết hôn 2018."
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeSession())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="thêm nữa tôi có con")
    assert captured["existing_facts_keys"] == ["ngay_ket_hon"]
    assert captured["case_type"] == "hôn nhân gia đình"
```

- [ ] **Step 2: Chạy test, confirm fail**

```bash
cd backend
pytest tests/services/test_chat_service.py -v
```

Expected: 3 new tests FAIL (chat_service chưa gọi two_stage_reason).

- [ ] **Step 3: Rewrite chat_service.py**

Ghi đè `backend/services/chat_service.py`:

```python
import logging

from services.qdrant_service import search_legal_context
from services.session_service import (
    add_fact,
    get_session,
    list_case_facts,
    save_message,
    update_session_case,
)
from services.two_stage_reasoner import two_stage_reason
from repositories.messages import list_recent_messages

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10
RETRIEVAL_TOP_K = 4
LOW_SCORE_THRESHOLD = 0.55


def _format_history_for_llm(messages) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _structured_to_display_text(structured: dict) -> str:
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


def _persist_extracted_facts(
    db,
    session_id: str,
    user_id: str,
    source_message_id: str,
    extracted: dict,
) -> None:
    for fact in extracted.get("extracted_facts", []) or []:
        if not fact.get("key") or fact.get("value") is None:
            continue
        add_fact(
            db,
            session_id=session_id,
            user_id=user_id,
            fact_key=fact["key"],
            fact_value=str(fact["value"]),
            source_message_id=source_message_id,
            confidence=float(fact.get("confidence", 1.0)),
        )


def _persist_case_update(
    db,
    session_id: str,
    user_id: str,
    case_type: str | None,
    case_summary: str | None,
    *,
    mark_intake_complete: bool = False,
) -> None:
    from datetime import datetime
    update_session_case(
        db,
        session_id=session_id,
        user_id=user_id,
        case_type=case_type,
        case_summary=case_summary,
        conversation_phase="consulting" if mark_intake_complete else None,
        intake_completed_at=datetime.utcnow() if mark_intake_complete else None,
    )


def send_chat_message(
    db,
    session_id: str,
    user_id: str,
    message: str,
) -> tuple[str, list[str], dict | None, dict | None]:
    """Main chat entry point.

    Returns (display_text, sources, structured, case_brief).
    """
    session = get_session(db, session_id, user_id)
    if session is None:
        raise ValueError("Session not found")

    # 1. Persist user turn first
    user_msg = save_message(db, session_id, user_id, "user", message)

    # 2. Load recent history
    recent = list_recent_messages(db, session_id, limit=HISTORY_LIMIT)
    history = _format_history_for_llm(recent[:-1])

    # 3. Load existing case facts
    existing_facts = list_case_facts(db, session_id)

    # 4. Retrieve legal context
    contexts = search_legal_context(message, top_k=RETRIEVAL_TOP_K)
    if not _is_retrieval_reliable(contexts):
        logger.info("Retrieval unreliable for session=%s", session_id)

    # 5. Two-stage reason
    try:
        result = two_stage_reason(
            message=message,
            contexts=contexts,
            history=history,
            existing_facts=existing_facts,
            case_type=getattr(session, "case_type", None),
            case_summary=getattr(session, "case_summary", None),
        )
    except ValueError as exc:
        logger.warning("Two-stage failed: %s", exc)
        from services.groq_service import generate_answer
        text = generate_answer(question=message, contexts=contexts, history=history)
        save_message(db, session_id, user_id, "assistant", text, {"sources": []})
        return text, [], None, None

    structured = result["structured"]
    extracted = result["extracted"]

    # 6. Persist extracted facts
    _persist_extracted_facts(db, session_id, user_id, user_msg.id, extracted)

    # 7. Persist case_type / case_summary update; mark intake complete if we got facts
    _persist_case_update(
        db,
        session_id,
        user_id,
        case_type=result.get("updated_case_type"),
        case_summary=result.get("updated_case_summary"),
        mark_intake_complete=bool(extracted.get("extracted_facts")),
    )

    # 8. Render display text
    display = _structured_to_display_text(structured)
    sources = [c.get("source_url", "") for c in contexts if c.get("source_url")]
    case_brief = {
        "case_type": result.get("updated_case_type"),
        "case_summary": result.get("updated_case_summary"),
        "facts": [{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in existing_facts],
    }
    save_message(
        db, session_id, user_id, "assistant", display,
        {"sources": sources, "structured": structured, "case_brief": case_brief},
    )
    return display, sources, structured, case_brief
```

- [ ] **Step 4: Cập nhật API route để trả 4-tuple**

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
    case_brief: dict | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    try:
        reply, sources, structured, case_brief = send_chat_message(
            db, request.session_id, str(current_user.id), request.message
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ChatResponse(reply=reply, sources=sources, structured=structured, case_brief=case_brief)
```

- [ ] **Step 5: Chạy test, confirm pass**

```bash
cd backend
pytest tests/services/ -v
```

Expected: tất cả PASS (test_chat_service có 7 test: 4 cũ + 3 mới; test_two_stage_reasoner 2; test_fact_extractor 5; test_groq_service 11; test_prompt_loader 3).

- [ ] **Step 6: Commit**

```bash
git add backend/services/chat_service.py backend/api/routes/chat.py backend/tests/services/test_chat_service.py
git commit -m "feat(chat): two-stage reasoning + persist case_facts + case_brief response"
```

---

## Task 2.6: Intake form frontend

**Files:**
- Create: `frontend/components/chat/intake-form.tsx`
- Modify: `frontend/lib/api.ts` (add intake API)
- Modify: `frontend/app/chat/[sessionId]/page.tsx` (gate on intake)
- Test: smoke manual

- [ ] **Step 1: Thêm intake API vào frontend/lib/api.ts**

Sửa `frontend/lib/api.ts` — thêm types và functions:

```typescript
export interface IntakeRequest {
  session_id: string
  case_type: string
  case_summary: string
  initial_facts: Array<{ key: string; value: string }>
}

export interface IntakeResponse {
  session_id: string
  case_type: string
  case_summary: string
  facts: Array<{ key: string; value: string; confidence: number }>
}

export async function submitIntake(req: IntakeRequest): Promise<IntakeResponse> {
  const res = await fetch(`${API_URL}/chat/intake`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể gửi thông tin ban đầu'))
  }
  return res.json()
}
```

- [ ] **Step 2: Tạo IntakeForm component**

Tạo `frontend/components/chat/intake-form.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { submitIntake, type IntakeResponse } from '@/lib/api'

const CASE_TYPES = [
  { value: 'hôn nhân gia đình', label: 'Hôn nhân & Gia đình' },
  { value: 'lao động', label: 'Lao động' },
  { value: 'đất đai', label: 'Đất đai & Nhà ở' },
  { value: 'hợp đồng', label: 'Hợp đồng dân sự' },
  { value: 'thừa kế', label: 'Thừa kế' },
  { value: 'hành chính', label: 'Hành chính' },
  { value: 'hình sự', label: 'Hình sự (sẽ chuyển luật sư chuyên môn)' },
  { value: 'khác', label: 'Khác' },
] as const

interface IntakeFormProps {
  sessionId: string
  onComplete: (resp: IntakeResponse) => void
}

export function IntakeForm({ sessionId, onComplete }: IntakeFormProps) {
  const [caseType, setCaseType] = useState('')
  const [caseSummary, setCaseSummary] = useState('')
  const [facts, setFacts] = useState<Array<{ key: string; value: string }>>([
    { key: '', value: '' },
  ])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const addFactRow = () => setFacts([...facts, { key: '', value: '' }])
  const removeFactRow = (i: number) => setFacts(facts.filter((_, idx) => idx !== i))
  const updateFact = (i: number, field: 'key' | 'value', val: string) => {
    const next = facts.slice()
    next[i] = { ...next[i], [field]: val }
    setFacts(next)
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!caseType) { setError('Vui lòng chọn loại vụ việc'); return }
    if (!caseSummary.trim()) { setError('Vui lòng tóm tắt vụ việc'); return }
    const cleanFacts = facts.filter(f => f.key.trim() && f.value.trim())
    setSubmitting(true)
    try {
      const resp = await submitIntake({
        session_id: sessionId,
        case_type: caseType,
        case_summary: caseSummary,
        initial_facts: cleanFacts,
      })
      onComplete(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi không xác định')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="intake-form" onSubmit={onSubmit} aria-labelledby="intake-heading">
      <h2 id="intake-heading">Bắt đầu tư vấn</h2>
      <p className="intake-hint">
        Trước khi tư vấn, luật sư cần biết loại vụ việc và một vài thông tin cơ bản.
        Bạn có thể bổ sung thêm trong quá trình chat.
      </p>

      <label className="intake-label">
        Loại vụ việc
        <select
          value={caseType}
          onChange={(e) => setCaseType(e.target.value)}
          required
        >
          <option value="">-- Chọn loại vụ --</option>
          {CASE_TYPES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </label>

      <label className="intake-label">
        Tóm tắt vụ việc
        <textarea
          value={caseSummary}
          onChange={(e) => setCaseSummary(e.target.value)}
          rows={4}
          placeholder="Ví dụ: Tôi kết hôn năm 2018, hiện muốn ly hôn đơn phương, có 1 con chung 3 tuổi..."
          required
        />
      </label>

      <fieldset className="intake-facts">
        <legend>Facts pháp lý ban đầu (tuỳ chọn)</legend>
        {facts.map((f, i) => (
          <div key={i} className="intake-fact-row">
            <input
              type="text"
              placeholder="key (vd: ngay_ket_hon)"
              value={f.key}
              onChange={(e) => updateFact(i, 'key', e.target.value)}
            />
            <input
              type="text"
              placeholder="giá trị (vd: 2018-03-15)"
              value={f.value}
              onChange={(e) => updateFact(i, 'value', e.target.value)}
            />
            <button type="button" onClick={() => removeFactRow(i)} aria-label="Xoá dòng">
              ✕
            </button>
          </div>
        ))}
        <button type="button" onClick={addFactRow}>+ Thêm fact</button>
      </fieldset>

      {error && <div role="alert" className="intake-error">{error}</div>}

      <button type="submit" disabled={submitting} className="intake-submit">
        {submitting ? 'Đang gửi...' : 'Bắt đầu tư vấn'}
      </button>
    </form>
  )
}
```

- [ ] **Step 3: Thêm endpoint /chat/intake vào backend**

Sửa `backend/api/routes/chat.py` — thêm cuối file:

```python
from dto.chat import IntakeRequest, IntakeResponse
from services.session_service import (
    add_fact,
    list_case_facts,
    update_session_case,
)
from datetime import datetime


@router.post("/chat/intake", response_model=IntakeResponse)
async def submit_intake(
    request: IntakeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntakeResponse:
    session = update_session_case(
        db,
        session_id=request.session_id,
        user_id=str(current_user.id),
        case_type=request.case_type,
        case_summary=request.case_summary,
        conversation_phase="consulting",
        intake_completed_at=datetime.utcnow(),
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    for fact in request.initial_facts:
        add_fact(
            db,
            session_id=request.session_id,
            user_id=str(current_user.id),
            fact_key=fact.key,
            fact_value=fact.value,
        )
    facts = list_case_facts(db, request.session_id)
    return IntakeResponse(
        session_id=request.session_id,
        case_type=session.case_type or "",
        case_summary=session.case_summary or "",
        facts=[{"key": f.fact_key, "value": f.fact_value, "confidence": f.confidence} for f in facts],
    )
```

- [ ] **Step 4: Tạo DTO IntakeRequest/Response**

Ghi `backend/dto/chat.py` (ghi đè):

```python
from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] | None = None
    structured: dict | None = None
    case_brief: dict | None = None


class IntakeFact(BaseModel):
    key: str
    value: str


class IntakeRequest(BaseModel):
    session_id: str
    case_type: str
    case_summary: str
    initial_facts: list[IntakeFact] = []


class IntakeFactOut(BaseModel):
    key: str
    value: str
    confidence: float


class IntakeResponse(BaseModel):
    session_id: str
    case_type: str
    case_summary: str
    facts: list[IntakeFactOut]
```

- [ ] **Step 5: Gate chat page khi chưa intake**

Sửa `frontend/app/chat/[sessionId]/page.tsx` (file hiện có — đọc trước khi sửa):

Tìm chỗ render chat UI; thêm gate ở đầu:

```tsx
import { useEffect, useState } from 'react'
import { IntakeForm } from '@/components/chat/intake-form'
import { getSession } from '@/lib/api'

// ... existing code ...

const [intakeDone, setIntakeDone] = useState(false)
const [sessionInfo, setSessionInfo] = useState<{ id: string } | null>(null)

useEffect(() => {
  // Load session info; backend should expose intake_completed_at
  // If not yet complete, show IntakeForm instead of chat composer.
  getSession(sessionId).then((s) => {
    setSessionInfo(s)
    setIntakeDone(true) // TEMP: assume done; Sprint 3 will wire intake_completed_at
  }).catch(() => {
    setIntakeDone(false)
  })
}, [sessionId])

if (!intakeDone) {
  return (
    <main>
      <IntakeForm
        sessionId={sessionId}
        onComplete={() => setIntakeDone(true)}
      />
    </main>
  )
}
```

> **Lưu ý kỹ thuật:** Backend chưa expose `intake_completed_at` qua `SessionResponse` DTO. Frontend tạm assume `intakeDone=true` để không break smoke test. **Task 2.6b** dưới đây sẽ fix.

- [ ] **Step 6: Thêm intake_completed_at vào SessionResponse DTO + frontend**

Sửa `backend/dto/session.py` (file hiện có):

```python
from datetime import datetime
from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    case_type: str | None = None
    case_summary: str | None = None
    conversation_phase: str | None = None
    intake_completed_at: datetime | None = None
```

Sửa `backend/api/routes/sessions.py` — populate thêm fields:

```python
return SessionResponse(
    id=str(s.id),
    user_id=str(s.user_id),
    title=s.title,
    case_type=s.case_type,
    case_summary=s.case_summary,
    conversation_phase=s.conversation_phase,
    intake_completed_at=s.intake_completed_at,
)
```

Sửa `frontend/lib/api.ts` — update `SessionResponse`:

```typescript
export interface SessionResponse {
  id: string
  user_id: string
  title: string
  case_type: string | null
  case_summary: string | null
  conversation_phase: string | null
  intake_completed_at: string | null
}
```

Sửa gate trong `frontend/app/chat/[sessionId]/page.tsx`:

```tsx
useEffect(() => {
  getSession(sessionId).then((s) => {
    setSessionInfo(s)
    setIntakeDone(Boolean(s.intake_completed_at))
  }).catch(() => setIntakeDone(false))
}, [sessionId])
```

- [ ] **Step 7: Smoke test thủ công**

```bash
cd backend
NEON_DATABASE_URL=<dev> alembic upgrade head
pytest -v
# Run backend
uvicorn main:app --reload
# Frontend
cd frontend && npm run dev
```

Test flow:
1. Tạo session mới → intake form hiện ra.
2. Điền form, submit → form biến mất, chat composer hiện ra.
3. Hỏi "thời hiệu ly hôn là bao lâu?" → bot trả lời có `tom_tat_vu_viec` reflect facts đã nhập.
4. Refresh page → intake form KHÔNG hiện lại (vì `intake_completed_at` đã set).
5. Hỏi tiếp "tôi có 1 con 3 tuổi" → check DB: `case_facts` table có row mới.

- [ ] **Step 8: Commit**

```bash
git add backend/dto/chat.py backend/dto/session.py backend/api/routes/chat.py backend/api/routes/sessions.py \
        frontend/lib/api.ts frontend/components/chat/intake-form.tsx frontend/app/chat/
git commit -m "feat(intake): backend endpoint + frontend form + session DTO fields"
```

---

## Self-review Sprint 2

- [ ] Tất cả test pass: `cd backend && pytest -v` — 22 (Sprint 1) + 3 entity + 2 repo + 5 extractor + 2 reasoner + 3 chat = **37 tests**.
- [ ] Migration Alembic upgrade + downgrade đều chạy thành công.
- [ ] `case_facts` table có index trên `session_id`.
- [ ] Có thể demo: tạo session → intake form → hỏi → bot nhớ facts → hỏi tiếp → bot dùng facts trong response.
- [ ] Không regression Sprint 1: persona prompt + structured output + history vẫn chạy.
- [ ] File lớn nhất (`chat_service.py`) < 200 dòng.
- [ ] `fact_extractor.py` + `two_stage_reasoner.py` mỗi file < 250 dòng.

---

## Kết thúc Sprint 2

Sau Sprint 2, hệ thống đáp ứng **~4/5** yêu cầu luật sư: clarify (qua intake + hỏi thêm), classify (case_type), research (RAG vẫn y nguyên), analyze (theo case_type), recommend + risk (trong structured response), cite (sources trả về). Còn thiếu: **citation verification chính xác** (chunk nào trích dẫn phải đúng chunk đó) và **UX chuyên nghiệp hơn** (chip click, suggested follow-ups, disclaimer banner). Đó là Sprint 3.
