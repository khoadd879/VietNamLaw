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