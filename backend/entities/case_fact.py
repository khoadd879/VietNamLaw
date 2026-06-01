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